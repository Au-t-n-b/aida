import os
os.environ["ZHIPU_SSL_VERIFY"] = "false"
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import llm
llm._llm_instance = None
print("verify=", llm._ssl_verify())
print("reply=", llm.chat_once("hi one word"))
