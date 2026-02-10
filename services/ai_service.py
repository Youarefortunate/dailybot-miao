import requests
from loguru import logger
from config import config

def summarize_with_doubao(text):
  """使用豆包 AI 总结文本内容"""
  url = config.DOUBAO_BASE_URL
  headers = {"Authorization": f"Bearer {config.DOUBAO_API_KEY}", "Content-Type": "application/json"}
  data = {
    "model": config.DOUBAO_MODEL,
    "messages": [
      {"role": "system", "content": "你是一个专业日报助手，请总结以下任务，使用列表形式，不要带 markdown 代码块。"},
      {"role": "user", "content": text}
    ],
  }
  try:
    resp = requests.post(url, headers=headers, json=data)
    return resp.json().get("choices", [{}])[0].get("message", {}).get("content", "总结失败")
  except Exception as e:
    logger.error(f"❌ AI 总结出错: {e}")
    return "总结失败"
