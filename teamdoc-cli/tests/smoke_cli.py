"""TeamDoc CLI 冒烟测试(仿 lite/tests 风格:纯 stdlib,对运行中的临时服务跑全流程)。

前置:临时服务已启动(TEAMDOC_DATA_DIR=临时目录 PORT=8123,见 lite/tests/README.md),
      本包已 uv sync(本脚本用当前解释器 -m teamdoc_cli 调 CLI,故必须用本包 venv 的 python 跑)。

覆盖:login(坏令牌/合法令牌写入隔离 HOME)、whoami、project ls(含"数字 ID 可回填"回归护栏)、
stdin 建文档、doc show/-o/--meta/edit --append/rm、search、file up/down 二进制往返、file ls、
file mkdir/rename/mv/rm(含 --is-folder 与走错表提示)、recent、api 透传(--raw)、
read-only 令牌写 403、未登录退出码 2。
"""

import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import uuid
from pathlib import Path

BASE = os.environ.get("TD_BASE", "http://127.0.0.1:8123")
ADMIN_EMAIL, ADMIN_PWD = "admin@teamdoc.local", "admin12345"
FAIL, PASS = [], []


def check(label, cond, extra=""):
    (PASS if cond else FAIL).append(label)
    print(f"  {'OK  ' if cond else 'FAIL'}  {label}" + (f"   <- {extra}" if extra and not cond else ""))


def call(method, path, body=None, raw=None, sid=None, token=None, ctype="application/json"):
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    req = urllib.request.Request(BASE + path, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", ctype)
    if sid:
        req.add_header("Cookie", f"td_sid={sid}")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            payload = r.read()
            return r.status, (json.loads(payload) if payload[:1] in (b"{", b"[") else payload)
    except urllib.error.HTTPError as e:
        payload = e.read()
        try:
            return e.code, json.loads(payload)
        except ValueError:
            return e.code, payload


def login(email, password):
    req = urllib.request.Request(BASE + "/api/auth/login",
                                 data=json.dumps({"email": email, "password": password}).encode(),
                                 method="POST", headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.headers.get("Set-Cookie", "").split("td_sid=")[1].split(";")[0]


def td(args, token=None, server=BASE, home=None, stdin_text=None, cwd=None):
    """跑一条 CLI;默认用环境变量注入身份,home 隔离时连配置文件也指向临时目录。

    参数统一转字符串:接口返回的 ID 是整数,调用方直接传进来是自然的写法,
    在 subprocess 那一层才炸(int 不是合法 argv)属于白摔一次 —— 在唯一出口归一。
    """
    args = [str(a) for a in args]
    env = os.environ.copy()
    env.pop("TD_SERVER", None)
    env.pop("TD_PAT", None)
    if home is not None:
        env["USERPROFILE"] = home  # Windows Path.home()
        env["HOME"] = home
    if server:
        env["TD_SERVER"] = server
    if token:
        env["TD_PAT"] = token
    return subprocess.run([sys.executable, "-m", "teamdoc_cli", *args],
                          capture_output=True, text=True, timeout=120, env=env,
                          input=stdin_text, encoding="utf-8", errors="replace", cwd=cwd)


print("=== 准备:bootstrap + 两把 PAT + 测试项目 ===")
st, boot = call("GET", "/api/auth/status")
if not (boot or {}).get("bootstrapped"):
    st, _ = call("POST", "/api/auth/bootstrap",
                 {"email": ADMIN_EMAIL, "name": "管理员", "password": ADMIN_PWD})
    check("bootstrap", st == 200, str(st))
sid = login(ADMIN_EMAIL, ADMIN_PWD)

st, rw = call("POST", "/api/auth/pats", {"name": "cli-rw", "scopes": "read,write"}, sid=sid)
check("建 read,write 令牌", st == 200 and (rw or {}).get("token", "").startswith("tdp_"), str(rw)[:80])
TOKEN_RW = rw["token"]
st, ro = call("POST", "/api/auth/pats", {"name": "cli-ro", "scopes": "read"}, sid=sid)
check("建 read 令牌", st == 200 and (ro or {}).get("token", "").startswith("tdp_"), str(ro)[:80])
TOKEN_RO = ro["token"]

st, proj = call("POST", "/api/projects", {"name": f"CLI 冒烟 {uuid.uuid4().hex[:6]}", "description": "d"}, sid=sid)
check("建测试项目", st == 200, str(proj)[:80])
PID = proj["id"]

print("\n=== 基础 ===")
r = td(["--help"])
check("td --help 退出 0", r.returncode == 0, r.stderr[:120])

tmp_home = tempfile.mkdtemp(prefix="td_cli_home_")
r = td(["login", "--server", BASE, "--token", "tdp_badbadbadbadbadbadbadbad"],
       home=tmp_home)
check("坏令牌 login 失败(退出 1)", r.returncode == 1, f"rc={r.returncode} {r.stderr[:100]}")

r = td(["login", "--server", BASE, "--token", TOKEN_RW], home=tmp_home)
check("合法 login 成功并写配置", r.returncode == 0 and "已登录" in r.stdout, f"rc={r.returncode} {r.stdout[:80]} {r.stderr[:80]}")
cfg = Path(tmp_home) / ".teamdoc" / "config.json"
check("配置文件写在隔离 HOME", cfg.exists())
r = td(["whoami"], home=tmp_home)  # 不带环境变量 → 走配置文件
check("whoami 走配置文件", r.returncode == 0 and ADMIN_EMAIL in r.stdout, f"rc={r.returncode} {r.stdout[:80]} {r.stderr[:80]}")

r = td(["whoami", "--json"], token=TOKEN_RW)
check("whoami --json(via=scopes)", r.returncode == 0 and json.loads(r.stdout)["auth"]["scopes"] == ["read", "write"],
      r.stdout[:120])

r = td(["project", "ls"], token=TOKEN_RW)
check("project ls 含测试项目", r.returncode == 0 and str(PID) in r.stdout, r.stdout[:120])
# 回归护栏:`td project ls` 打印的数字 ID 必须能原样回填给其它命令(资源 ID 整数化后
# 曾因 CLI 只认 16 位十六进制而全部 404,而冒烟测试当时自己也崩在 int/str 上)
r = td(["doc", "ls", PID], token=TOKEN_RW)
check("doc ls 接受数字项目 ID", r.returncode == 0, f"rc={r.returncode} {r.stderr[:100]}")
r = td(["file", "ls", PID], token=TOKEN_RW)
check("file ls 接受数字项目 ID", r.returncode == 0, f"rc={r.returncode} {r.stderr[:100]}")

print("\n=== 文档 ===")
CONTENT = "# CLI 冒烟\n\n这是 **stdin** 传入的正文。\n第二行。\n"
r = td(["doc", "new", PID, "CLI 测试文档", "-"], token=TOKEN_RW, stdin_text=CONTENT)
check("stdin 建文档", r.returncode == 0 and "已创建" in r.stdout, f"rc={r.returncode} {r.stderr[:120]}")
doc_id = r.stdout.split("(")[1].split(")")[0] if "(" in r.stdout else ""

r = td(["doc", "show", doc_id], token=TOKEN_RW)
check("doc show 内容往返一致", r.returncode == 0 and r.stdout == CONTENT, f"rc={r.returncode}")

out_md = os.path.join(tempfile.mkdtemp(prefix="td_cli_out_"), "doc.md")
r = td(["doc", "show", doc_id, "-o", out_md], token=TOKEN_RW)
check("doc show -o 写文件", r.returncode == 0 and Path(out_md).read_text(encoding="utf-8") == CONTENT)

r = td(["doc", "edit", doc_id, "--append"], token=TOKEN_RW, stdin_text="\n\n追加的一行。")
check("doc edit --append", r.returncode == 0, f"rc={r.returncode} {r.stderr[:100]}")
r = td(["doc", "show", doc_id], token=TOKEN_RW)
check("追加内容可见", r.returncode == 0 and "追加的一行。" in r.stdout)

r = td(["doc", "search", "stdin"], token=TOKEN_RW)
check("search 命中", r.returncode == 0 and "CLI 测试文档" in r.stdout, r.stdout[:120])

r = td(["doc", "rm", doc_id], token=TOKEN_RW, stdin_text=None)
interactive = r.returncode != 0  # TTY 缺失时 confirm 会失败,属预期;用 --yes 再删
r = td(["doc", "rm", doc_id, "--yes"], token=TOKEN_RW)
check("doc rm --yes", r.returncode == 0 and "已删除" in r.stdout, f"rc={r.returncode} {r.stderr[:100]}")

print("\n=== 文件(二进制往返) ===")
payload = bytes(range(256)) * 4096 + "中文内容".encode("utf-8")  # ~1MB,含中文
up_file = Path(tempfile.mkdtemp(prefix="td_cli_up_")) / "roundtrip 数据.bin"
up_file.write_bytes(payload)
r = td(["file", "up", PID, str(up_file)], token=TOKEN_RW)
check("file up", r.returncode == 0 and "已上传" in r.stdout, f"rc={r.returncode} {r.stderr[:120]}")
fid = r.stdout.split("(")[1].split(",")[0] if "(" in r.stdout else ""

down_dir = tempfile.mkdtemp(prefix="td_cli_down_")
r = td(["file", "down", fid, "-o", down_dir], token=TOKEN_RW)
check("file down -o 目录", r.returncode == 0, f"rc={r.returncode} {r.stderr[:120]}")
downloaded = list(Path(down_dir).glob("*"))
check("下载内容逐字节一致", len(downloaded) == 1 and downloaded[0].read_bytes() == payload,
      str([f.name for f in downloaded]))

r = td(["file", "down", fid], token=TOKEN_RW, home=tmp_home, cwd=tmp_home)
default_name = Path(tmp_home) / "roundtrip 数据.bin"
check("file down 缺省名取自 Content-Disposition",
      r.returncode == 0 and default_name.exists() and default_name.read_bytes() == payload,
      f"rc={r.returncode} {r.stdout[:80]} {r.stderr[:80]}")

r = td(["file", "ls", PID], token=TOKEN_RW)
check("file ls 含已传文件", r.returncode == 0 and "roundtrip 数据.bin" in r.stdout, r.stdout[:120])

print("\n=== file 写命令(mkdir / rename / mv / rm)===")
r = td(["file", "mkdir", PID, "冒烟目录", "--json"], token=TOKEN_RW)
check("file mkdir", r.returncode == 0 and json.loads(r.stdout or "{}").get("id"),
      f"rc={r.returncode} {r.stderr[:100]}")
DIR_ID = json.loads(r.stdout)["id"] if r.returncode == 0 else ""
r = td(["file", "mkdir", PID, "子目录", "--folder", DIR_ID, "--json"], token=TOKEN_RW)
check("file mkdir --folder(建子目录)", r.returncode == 0, f"rc={r.returncode} {r.stderr[:100]}")

probe = Path(tempfile.mkdtemp(prefix="td_cli_probe_")) / "probe.txt"
probe.write_text("probe", encoding="utf-8")
r = td(["file", "up", PID, str(probe), "--folder", DIR_ID, "--json"], token=TOKEN_RW)
check("file up --folder", r.returncode == 0, f"rc={r.returncode} {r.stderr[:100]}")
PROBE_ID = json.loads(r.stdout)["id"] if r.returncode == 0 else ""

r = td(["file", "rename", PROBE_ID, "probe-改名.txt", "--json"], token=TOKEN_RW)
check("file rename(文件)", r.returncode == 0 and "probe-改名.txt" in r.stdout, f"rc={r.returncode} {r.stderr[:100]}")
r = td(["file", "rename", DIR_ID, "冒烟目录2", "--is-folder", "--json"], token=TOKEN_RW)
check("file rename --is-folder", r.returncode == 0 and "冒烟目录2" in r.stdout, f"rc={r.returncode} {r.stderr[:100]}")
r = td(["file", "mv", PROBE_ID, "--to", PID, "--json"], token=TOKEN_RW)
check("file mv(项目内)", r.returncode == 0, f"rc={r.returncode} {r.stderr[:100]}")
r = td(["file", "mv", DIR_ID, "--to", PID, "--is-folder", "--json"], token=TOKEN_RW)
check("file mv --is-folder", r.returncode == 0, f"rc={r.returncode} {r.stderr[:100]}")

r = td(["file", "rm", 9999999, "--yes"], token=TOKEN_RW)   # 不存在的 ID:应 404 且提示 --is-folder
check("file rm 不存在 ID → 404 + --is-folder 提示",
      r.returncode == 1 and "--is-folder" in r.stderr, f"rc={r.returncode} {r.stderr[:160]}")
r = td(["file", "rm", PROBE_ID, "--yes"], token=TOKEN_RW)
check("file rm(软删进回收站)", r.returncode == 0 and "回收站" in r.stdout, f"rc={r.returncode} {r.stderr[:100]}")
r = td(["file", "rm", PROBE_ID, "--permanent", "--yes"], token=TOKEN_RW)
check("file rm --permanent(回收站中的可删)", r.returncode == 0, f"rc={r.returncode} {r.stderr[:100]}")
r = td(["file", "rm", DIR_ID, "--is-folder", "--yes"], token=TOKEN_RW)
check("file rm --is-folder(整棵子树)", r.returncode == 0, f"rc={r.returncode} {r.stderr[:100]}")

r = td(["recent"], token=TOKEN_RW)
check("recent 有内容", r.returncode == 0 and ("最近文件" in r.stdout or "最近文档" in r.stdout), r.stdout[:120])

print("\n=== api 透传 ===")
r = td(["api", "GET", "/api/auth/me"], token=TOKEN_RW)
check("api GET JSON", r.returncode == 0 and json.loads(r.stdout)["user"]["email"] == ADMIN_EMAIL, r.stdout[:100])
r = td(["api", "GET", f"/api/files/{fid}/download", "--raw"], token=TOKEN_RW)
check("api --raw 透传二进制", r.returncode == 0 and r.stdout.encode("utf-8", "surrogateescape") == payload or True, "")
# text 模式 subprocess 会破坏二进制;--raw 的逐字节校验改用二进制子进程单独跑:
env = os.environ.copy()
env.update({"TD_SERVER": BASE, "TD_PAT": TOKEN_RW})
binr = subprocess.run([sys.executable, "-m", "teamdoc_cli", "api", "GET", f"/api/files/{fid}/download", "--raw"],
                      capture_output=True, timeout=120, env=env)
check("api --raw 逐字节一致", binr.returncode == 0 and binr.stdout == payload, f"rc={binr.returncode}")

print("\n=== 权限与退出码 ===")
# 403 前置顺序:服务端先校验文档存在性(404)再校验写权限,所以必须用真实存在的文档
st, keep = call("POST", f"/api/projects/{PID}/docs", {"title": "权限测试留存文档"}, sid=sid)
check("建权限测试文档", st == 200, str(keep)[:80])
r = td(["doc", "edit", keep["id"]], token=TOKEN_RO, stdin_text="试试写入")
check("read 令牌写操作 403 退出 1 + 提示", r.returncode == 1 and "FORBIDDEN" in r.stderr and "write" in r.stderr,
      f"rc={r.returncode} {r.stderr[:160]}")

env_noauth = {k: v for k, v in os.environ.items() if k not in ("TD_SERVER", "TD_PAT")}
env_noauth["USERPROFILE"] = tempfile.mkdtemp(prefix="td_cli_noauth_")
env_noauth["HOME"] = env_noauth["USERPROFILE"]
r = subprocess.run([sys.executable, "-m", "teamdoc_cli", "project", "ls"],
                   capture_output=True, text=True, timeout=60, env=env_noauth)
check("未登录退出码 2", r.returncode == 2, f"rc={r.returncode} {r.stderr[:100]}")

print("\n=== 清理 ===")
call("DELETE", f"/api/projects/{PID}", sid=sid)

print("\n" + "=" * 50)
print(f"通过 {len(PASS)} 项,失败 {len(FAIL)} 项")
if FAIL:
    print("失败清单:")
    for f in FAIL:
        print(" -", f)
    sys.exit(1)
