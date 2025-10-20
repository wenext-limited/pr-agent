#创建一个http高性能代理，接收http请求后创建子进程执行命令 python pr_agent/cli.py


#创建一个http高性能代理，接收http请求后创建子进程执行命令 python pr_agent/cli.py

import os
import sys
import json
import subprocess
from typing import Any, Dict, List
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

app = FastAPI()

#python pr_agent/cli.py improve --pr_url https://github.com/wenext-limited/game-platform/pull/64  --num_max_findings=10


def _build_args(payload: Dict[str, Any]) -> List[str]:
    args: List[str] = []

    pr_url = payload.get("pr_url")
    if not pr_url:
        raise HTTPException(status_code=400, detail="pr_url is required")

    # 默认使用示例中的命令 improve；也可通过 body 指定其他命令
    command = str(payload.get("command", "improve"))
    args.append(command)

    # 必填参数
    args.append(f"--pr_url={pr_url}")

    # 其他透传参数
    rest = payload.get("rest", [])
    if isinstance(rest, list):
        args.extend([str(x) for x in rest])
    elif isinstance(rest, str):
        args.append(rest)

    return args



def _spawn_cli(args: List[str], extra_env: Dict[str, str] | None = None) -> int:
    popen_kwargs: Dict[str, Any] = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "close_fds": True,
    }
    if os.name == "nt":
        popen_kwargs["creationflags"] = 0x00000008 | 0x00000200
    else:
        popen_kwargs["start_new_session"] = True

    env = os.environ.copy()
    if extra_env:
        for k, v in extra_env.items():
            if v is not None:
                env[str(k)] = str(v)

    proc = subprocess.Popen([sys.executable, "pr_agent/cli.py", *args], env=env, **popen_kwargs)
    return proc.pid


@app.post("/invoke")
async def invoke(request: Request):
    payload = await request.json()
    args = _build_args(payload)

        # 从配置目录读取 KEY=VALUE 环境变量（/app/config 下的所有文件）
    extra_env = {}
    config_dir = "/app/config"
    try:
        if os.path.isdir(config_dir):
            for name in os.listdir(config_dir):
                if name != "env":
                    continue
                file_path = os.path.join(config_dir, name)
                if not os.path.isfile(file_path):
                    continue
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if not line or line.startswith("#"):
                                continue
                            if "=" not in line:
                                continue
                            k, v = line.split("=", 1)
                            k = k.strip()
                            v = v.strip().strip('"').strip("'")
                            if k:
                                extra_env[k] = v
                except Exception:
                    # 忽略单个文件读取/解析异常
                    pass
    except Exception:
        # 忽略目录不存在等异常
        pass

    pid = _spawn_cli(args, extra_env=extra_env)
    return JSONResponse(status_code=202, content={"status": "accepted", "pid": pid})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))