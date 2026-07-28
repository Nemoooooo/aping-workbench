#!/usr/bin/env python3.11
"""
每日自动生成调度器（阿萍的工作台）
- 每天 07:00（Asia/Shanghai）重新生成「每日新闻联播深度分析」
- 每天 09:00（Asia/Shanghai）重新生成「AI动态每日简报」
数据写入 /workspace/data，由沙箱 8000 端口直接对外提供（手机可访问）。
若配置了有效 GitHub Token（环境变量 GH_TOKEN 或远程地址含 token），
则额外把更新推送到 GitHub Pages 作为镜像。
"""
import os
import time
import subprocess
import datetime

REPO_DIR = "/tmp/deploy"
import sys
PY = sys.executable
BRANCH = "main"
REMOTE = "origin"
TOKEN = os.environ.get("GH_TOKEN", "")


def sh(cmd, cwd=REPO_DIR):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def ensure_remote_token():
    if TOKEN:
        url = f"https://x-access-token:{TOKEN}@github.com/Nemoooooo/aping-workbench.git"
        sh(["git", "remote", "set-url", REMOTE, url])


def run_generate():
    r = sh([PY, "scripts/generate.py"])
    return r.returncode == 0, r.stderr


def git_push(date_str):
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
    last_news = ""
    last_ai = ""
    mode = "（含 GitHub Pages 推送）" if can_push else "（仅沙箱本地，供手机直接访问）"
    print(f"[{now_shanghai():%Y-%m-%d %H:%M:%S}] 调度器启动 {mode}", flush=True)
    while True:
        try:
            t = now_shanghai()
            hhmm = t.strftime("%H:%M")
            today = t.strftime("%Y-%m-%d")
            if hhmm == "07:00" and last_news != today:
                ok, msg = run_generate()
                if ok:
                    if can_push:
                        ok2, msg2 = git_push(today)
                        print(f"[{t:%H:%M:%S}] 07:00 新闻分析 {'已推送' if ok2 else '推送失败'}: {msg2[:80]}", flush=True)
                    else:
                        print(f"[{t:%H:%M:%S}] 07:00 新闻分析已重新生成（本地）", flush=True)
                else:
                    print(f"[{t:%H:%M:%S}] 07:00 生成失败: {msg[:120]}", flush=True)
                last_news = today
            if hhmm == "09:00" and last_ai != today:
                ok, msg = run_generate()
                if ok:
                    if can_push:
                        ok2, msg2 = git_push(today)
                        print(f"[{t:%H:%M:%S}] 09:00 AI简报 {'已推送' if ok2 else '推送失败'}: {msg2[:80]}", flush=True)
                    else:
                        print(f"[{t:%H:%M:%S}] 09:00 AI简报已重新生成（本地）", flush=True)
                else:
                    print(f"[{t:%H:%M:%S}] 09:00 生成失败: {msg[:120]}", flush=True)
                last_ai = today
        except Exception as e:
            print(f"[scheduler error] {e}", flush=True)
        time.sleep(30)


if __name__ == "__main__":
    main()
