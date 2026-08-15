#!/bin/zsh

SCRIPT_DIR=${0:A:h}
cd "$SCRIPT_DIR" || exit 1

if [ ! -x ".venv/bin/python" ]; then
  echo "首次运行：正在创建独立Python环境……"
  python3 -m venv .venv
  if [ $? -ne 0 ]; then
    echo "创建Python环境失败，请确认已经安装Python 3。"
    read -k 1 "REPLY?按任意键关闭……"
    exit 1
  fi

  echo "正在安装requests依赖……"
  .venv/bin/python -m pip install -r requirements.txt
  if [ $? -ne 0 ]; then
    echo "安装依赖失败，请检查网络。"
    read -k 1 "REPLY?按任意键关闭……"
    exit 1
  fi
fi

.venv/bin/python app.py

echo ""
read -k 1 "REPLY?按任意键关闭窗口……"
echo ""
