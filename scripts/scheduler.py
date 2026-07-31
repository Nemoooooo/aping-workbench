#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""
每日自动生成调度器（阿萍的工作台）
- 每天 07:00（Asia/Shanghai）重新生成「每日新闻联播深度分析」
- 每天 09:00（Asia/Shanghai）重新生成「AI动态每日简报」

Cloud Studio 沙箱会在闲置时休眠、恢复后继续运行。因此本调度器增加：
1. 启动/恢复时检查是否漏跑，若当前时间已过调度点则立即补跑；
2. 把 last_news / last_ai / pushed 持久化到 .scheduler_state.json；
3. 【关键修复】推送失败不再标记当天完成——只要本地还有未推送的提交，
   调度器每 30s 持续重试推送，直到 GitHub 可达，避免数据滞留。
"""
import os
import time
import subprocess
import datetime
import json

REPO_DIR = "/tmp/deploy"
import sys
PY = sys.executable
BRANCH = "main"
REMOTE = "origin"
TOKEN = os.environ.get("GH_TOKEN", "")
STATE_FILE = os.path.join("/workspace", ".scheduler_state.json")


def sh(cmd, cwd=REPO_DIR):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def ensure_remote_token():
    if TOKEN:
        url = f"https://x-access-token:{TOKEN}@github.com/Nemoooooo/aping-workbench.git"
        sh(["git", "remote", "set-url", REMOTE, url])


def load_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(state):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False)
    except Exception as e:
        print(f"[{now_shanghai():%Y-%m-%d %H:%M:%S}] 状态保存失败: {e}", flush=True)


def run_generate():
    r = sh([PY, "scripts/generate.py"])
    return r.returncode == 0, r.stdout + r.stderr


def _sync_file(rel):
    sp = os.path.join("/workspace", rel)
    dp = os.path.join(REPO_DIR, rel)
    if not os.path.exists(sp):
        return
    os.makedirs(os.path.dirname(dp), exist_ok=True)
    with open(sp, "r", encoding="utf-8") as f:
        content = f.read()
    with open(dp, "w", encoding="utf-8") as f:
        f.write(content)


def git_push(date_str):
    # 同步 /workspace 下的关键文件到部署仓库（含内嵌保险数据的 index.html）
    for rel in ["index.html", "service-worker.js", "manifest.webmanifest",
                os.path.join("scripts", "generate.py"),
                os.path.join("scripts", "scheduler.py")]:
        _sync_file(rel)
    # generate.py 写入 /workspace/data，需先同步进部署仓库
    src = os.path.join("/workspace", "data")
    dst = os.path.join(REPO_DIR, "data")
    if os.path.isdir(src):
        os.makedirs(dst, exist_ok=True)
        for fn in os.listdir(src):
            if fn.endswith(".json"):
                with open(os.path.join(src, fn), "r", encoding="utf-8") as f:
                    data = f.read()
                with open(os.path.join(dst, fn), "w", encoding="utf-8") as f:
                    f.write(data)
    sh(["git", "add", "-A"])
    st = sh(["git", "status", "--porcelain"])
    if st.stdout.strip():
        sh(["git", "-c", "credential.helper=", "commit",
            "-m", f"daily auto-update {date_str}"])
    # 始终尝试推送（即便只是把已提交但未推上去的本地提交推到远端）
    r = sh(["git", "-c", "credential.helper=", "push", REMOTE, BRANCH])
    if r.returncode != 0:
        return False, (r.stderr or r.stdout)
    return True, "ok"


def push_enabled():
    if TOKEN:
        return True
    r = sh(["git", "remote", "get-url", REMOTE])
    return "@" in r.stdout.strip()


def now_shanghai():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))


def main():
    ensure_remote_token()
    can_push = push_enabled()
    state = load_state()
    mode = "（含 GitHub Pages 推送）" if can_push else "（仅沙箱本地，供手机直接访问）"
    print(f"[{now_shanghai():%Y-%m-%d %H:%M:%S}] 调度器启动 {mode}", flush=True)
    print(f"[{now_shanghai():%Y-%m-%d %H:%M:%S}] 状态: last_news={state.get('last_news','')}, "
          f"last_ai={state.get('last_ai','')}, pushed={state.get('pushed','')}", flush=True)

    def try_push(today):
        if state.get("pushed") == today:
            return True
        ok2, msg2 = git_push(today)
        if ok2:
            state["pushed"] = today
            save_state(state)
            print(f"[{now_shanghai():%H:%M:%S}] 已推送至 GitHub Pages", flush=True)
        else:
            print(f"[{now_shanghai():%H:%M:%S}] 推送失败（将每周期重试）: {str(msg2)[:90]}", flush=True)
        return ok2

    def run_news(today):
        ok, msg = run_generate()
        if ok:
            state["last_news"] = today
            save_state(state)
            print(f"[{now_shanghai():%H:%M:%S}] 新闻分析已重新生成（本地 {today}）", flush=True)
            if can_push:
                try_push(today)
        else:
            print(f"[{now_shanghai():%H:%M:%S}] 新闻分析生成失败: {msg[:200]}", flush=True)

    def run_ai(today):
        ok, msg = run_generate()
        if ok:
            state["last_ai"] = today
            save_state(state)
            print(f"[{now_shanghai():%H:%M:%S}] AI简报已重新生成（本地 {today}）", flush=True)
            if can_push:
                try_push(today)
        else:
            print(f"[{now_shanghai():%H:%M:%S}] AI简报生成失败: {msg[:200]}", flush=True)

    while True:
        try:
            t = now_shanghai()
            hhmm = t.strftime("%H:%M")
            today = t.strftime("%Y-%m-%d")

            # 新闻联播：07:00 执行；若沙箱恢复时间晚于 07:00 则立即补跑
            if state.get("last_news") != today and hhmm >= "07:00":
                run_news(today)

            # AI 简报：09:00 执行；若沙箱恢复时间晚于 09:00 则立即补跑
            if state.get("last_ai") != today and hhmm >= "09:00":
                run_ai(today)

            # 独立推送重试：只要今天已生成、且尚未成功推送，就持续尝试（修复“推送失败即标记完成”的缺陷）
            if can_push and state.get("pushed") != today and (
                    state.get("last_news") == today or state.get("last_ai") == today):
                try_push(today)

        except Exception as e:
            print(f"[{now_shanghai():%Y-%m-%d %H:%M:%S}] [scheduler error] {e}", flush=True)
        time.sleep(30)


if __name__ == "__main__":
    main()
