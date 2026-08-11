#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""
每日自动生成调度器（阿萍的工作台）
- 每天 07:00 重新生成「每日新闻联播深度分析」
- 每天 09:00 重新生成「AI动态每日简报」

部署通道（双通道）：
- 主用 Gitee Pages（国内可达，手机直连）：推送到 gitee 远程（main -> master）
- 备用 GitHub Pages（沙箱常被墙，尽力推送）：推送到 origin 远程

Cloud Studio 沙箱会休眠、恢复后继续运行。本调度器：
1. 启动/恢复时检查是否漏跑，立即补跑；
2. last_news / last_ai / pushed 持久化；
3. 推送失败不标记当天完成，每 30s 持续重试，直到可达。
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
GITEE_REPO = "cui-pingnemo/aping-workbench"
GITEE_TOKEN_FILE = "/root/.gitee_token"
STATE_FILE = os.path.join("/workspace", ".scheduler_state.json")
CLOUDFLARE_LOG = "/tmp/preview-cloudflared.log"
CONFIG_FILE = os.path.join("/workspace", "config.json")


def sh(cmd, cwd=REPO_DIR):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def sht(cmd, timeout=30, cwd=REPO_DIR):
    """带超时执行，避免 GitHub 不可达时 git push 长时间挂起阻塞调度循环"""
    try:
        return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(cmd, returncode=-1, stdout="", stderr="timeout")


def ensure_remote_token():
    if TOKEN:
        url = f"https://x-access-token:{TOKEN}@github.com/Nemoooooo/aping-workbench.git"
        sh(["git", "remote", "set-url", REMOTE, url])


def ensure_gitee_remote():
    try:
        tok = open(GITEE_TOKEN_FILE, encoding="utf-8").read().strip()
    except Exception:
        return
    if not tok:
        return
    url = f"https://oauth2:{tok}@gitee.com/{GITEE_REPO}.git"
    sh(["git", "remote", "remove", "gitee"])
    sh(["git", "remote", "add", "gitee", url])


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


def detect_tunnel_url():
    """从 cloudflared 日志中提取最新的 trycloudflare 隧道地址"""
    try:
        with open(CLOUDFLARE_LOG, "r", encoding="utf-8", errors="ignore") as f:
            txt = f.read()
        urls = [u for u in __import__("re").findall(r"https://[a-z0-9-]+\.trycloudflare\.com", txt)
                if "api.trycloudflare" not in u]
        return urls[-1] if urls else ""
    except Exception:
        return ""


def update_backend_config():
    """检测当前隧道地址，若变化则更新 config.json 并推送到部署仓库（让 PWA 读到最新后端）"""
    url = detect_tunnel_url()
    if not url:
        return False
    try:
        cur = {}
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cur = json.load(f)
        if cur.get("backend") == url:
            return False
        cur["backend"] = url
        cur["updated"] = now_shanghai().strftime("%Y-%m-%d")
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cur, f, ensure_ascii=False, indent=2)
        # 同步并推送 config.json
        _sync_file("config.json")
        sh(["git", "-C", REPO_DIR, "add", "-A"])
        sh(["git", "-C", REPO_DIR, "commit", "-m", "chore: update backend tunnel url"])
        r_gitee = sh(["git", "-c", "credential.helper=", "push", "gitee", "main:master"])
        r_gh = sh(["git", "-c", "credential.helper=", "push", REMOTE, BRANCH])
        print(f"[{now_shanghai():%H:%M:%S}] 后端地址已更新并推送: {url}", flush=True)
        return True
    except Exception as e:
        print(f"[{now_shanghai():%H:%M:%S}] 更新后端配置失败: {e}", flush=True)
        return False


def git_push(date_str):
    # 同步 /workspace 关键文件到部署仓库
    for rel in ["index.html", "service-worker.js", "manifest.webmanifest", "config.json",
                os.path.join("scripts", "generate.py"),
                os.path.join("scripts", "scheduler.py")]:
        _sync_file(rel)
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
    ensure_gitee_remote()
    sh(["git", "add", "-A"])
    st = sh(["git", "status", "--porcelain"])
    if st.stdout.strip():
        sh(["git", "-c", "credential.helper=", "commit",
            "-m", f"daily auto-update {date_str}"])
    # 双通道推送：GitHub Pages（稳定永久地址，手机直连）+ Gitee（国内备用）
    # 二者任一成功即视为推送完成，最大化可用性
    r_gitee = sh(["git", "-c", "credential.helper=", "push", "gitee", "main:master"])
    r_gh = sht(["git", "-c", "credential.helper=", "push", REMOTE, BRANCH], timeout=25)
    ok = r_gitee.returncode == 0 or r_gh.returncode == 0
    if ok:
        channels = []
        if r_gh.returncode == 0:
            channels.append("github")
        if r_gitee.returncode == 0:
            channels.append("gitee")
        return True, "ok (" + "+".join(channels) + ")"
    return False, ((r_gh.stderr or "") + (r_gitee.stderr or "") or "push failed")


def push_enabled():
    # GitHub 与 Gitee 任一可用即认为可推送
    if TOKEN:
        return True
    if os.path.exists(GITEE_TOKEN_FILE):
        return True
    r = sh(["git", "remote", "get-url", REMOTE])
    return "@" in r.stdout.strip()


def now_shanghai():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))


def unpushed_count():
    """本地领先 origin/main 的提交数（git push 会更新远程跟踪引用，故可本地判断）"""
    r = sh(["git", "rev-list", "--count", "origin/main..HEAD"])
    try:
        return int((r.stdout or "0").strip() or 0)
    except Exception:
        return 0


def main():
    ensure_remote_token()
    ensure_gitee_remote()
    can_push = push_enabled()
    state = load_state()
    mode = "（Gitee 主用 + GitHub 备用）" if can_push else "（仅本地）"
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
            print(f"[{now_shanghai():%H:%M:%S}] 已推送（Gitee 主用）", flush=True)
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

            # 后端隧道地址自检：变化则更新 config.json 并推送（保证备忘录云端备份不断）
            update_backend_config()

            # 本地有未推送 GitHub 的提交（如本次备忘录云端功能）则持续补齐，
            # 网络恢复后自动推上 GitHub Pages，无需等待下次每日生成
            if unpushed_count() > 0:
                rp = sht(["git", "-c", "credential.helper=", "push", REMOTE, BRANCH], timeout=25)
                if rp.returncode == 0:
                    print(f"[{now_shanghai():%H:%M:%S}] 已补齐推送至 GitHub Pages（含未上线改动）", flush=True)
                else:
                    print(f"[{now_shanghai():%H:%M:%S}] GitHub 暂不可达，稍后自动重试补齐", flush=True)

            if state.get("last_news") != today and hhmm >= "07:00":
                run_news(today)
            if state.get("last_ai") != today and hhmm >= "09:00":
                run_ai(today)
            # 独立推送重试：今天已生成且未成功推送则持续重试
            if can_push and state.get("pushed") != today and (
                    state.get("last_news") == today or state.get("last_ai") == today):
                try_push(today)
        except Exception as e:
            print(f"[{now_shanghai():%Y-%m-%d %H:%M:%S}] [scheduler error] {e}", flush=True)
        time.sleep(30)


if __name__ == "__main__":
    main()
