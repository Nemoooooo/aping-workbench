#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""
每日自动生成调度器（阿萍的工作台）
- 每天 07:00（Asia/Shanghai）重新生成「每日新闻联播深度分析」
- 每天 09:00（Asia/Shanghai）重新生成「AI动态每日简报」

Cloud Studio 沙箱会在闲置时休眠、恢复后继续运行。因此本调度器增加：
1. 启动/恢复时检查是否漏跑，若当前时间已过调度点则立即补跑；
2. 把 last_news / last_ai 持久化到 .scheduler_state.json，避免进程重启后状态丢失。
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
    if not st.stdout.strip():
        return True, "无变更"
    sh(["git", "-c", "credential.helper=", "commit",
        "-m", f"daily auto-update {date_str}"])
    r = sh(["git", "-c", "credential.helper=", "push", REMOTE, BRANCH])
    return r.returncode == 0, r.stderr


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
    last_news = state.get("last_news", "")
    last_ai = state.get("last_ai", "")
    mode = "（含 GitHub Pages 推送）" if can_push else "（仅沙箱本地，供手机直接访问）"
    print(f"[{now_shanghai():%Y-%m-%d %H:%M:%S}] 调度器启动 {mode}", flush=True)
    print(f"[{now_shanghai():%Y-%m-%d %H:%M:%S}] 状态: last_news={last_news}, last_ai={last_ai}", flush=True)

    def run_news(today):
        nonlocal last_news
        ok, msg = run_generate()
        if ok:
            if can_push:
                ok2, msg2 = git_push(today)
                print(f"[{now_shanghai():%H:%M:%S}] 新闻分析 {'已推送' if ok2 else '推送失败'}: {msg2[:80]}", flush=True)
            else:
                print(f"[{now_shanghai():%H:%M:%S}] 新闻分析已重新生成（本地）", flush=True)
            last_news = today
            save_state({"last_news": last_news, "last_ai": last_ai})
        else:
            print(f"[{now_shanghai():%H:%M:%S}] 新闻分析生成失败: {msg[:200]}", flush=True)

    def run_ai(today):
        nonlocal last_ai
        ok, msg = run_generate()
        if ok:
            if can_push:
                ok2, msg2 = git_push(today)
                print(f"[{now_shanghai():%H:%M:%S}] AI简报 {'已推送' if ok2 else '推送失败'}: {msg2[:80]}", flush=True)
            else:
                print(f"[{now_shanghai():%H:%M:%S}] AI简报已重新生成（本地）", flush=True)
            last_ai = today
            save_state({"last_news": last_news, "last_ai": last_ai})
        else:
            print(f"[{now_shanghai():%H:%M:%S}] AI简报生成失败: {msg[:200]}", flush=True)

    while True:
        try:
            t = now_shanghai()
            hhmm = t.strftime("%H:%M")
            today = t.strftime("%Y-%m-%d")

            # 新闻联播：07:00 执行；若沙箱恢复时间晚于 07:00 则立即补跑
            if last_news != today and hhmm >= "07:00":
                run_news(today)

            # AI 简报：09:00 执行；若沙箱恢复时间晚于 09:00 则立即补跑
            if last_ai != today and hhmm >= "09:00":
                run_ai(today)

        except Exception as e:
            print(f"[{now_shanghai():%Y-%m-%d %H:%M:%S}] [scheduler error] {e}", flush=True)
        time.sleep(30)


if __name__ == "__main__":
    main()
