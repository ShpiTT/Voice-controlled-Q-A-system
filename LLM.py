# coding=utf-8
"""
大语言模型模块
功能：指令标准化转换、意图识别、聊天问答
"""

import os
import json
from openai import OpenAI

# 尝试加载 .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# API配置
API_KEY = os.getenv("ALI_API_KEY", "")
BASE_URL = os.getenv("ALI_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
MODEL = os.getenv("ALI_MODEL", "qwen-flash")

# 读取标准指令文件
def load_instruction_file():
    """加载标准指令示范文本"""
    file_path = os.path.join(os.path.dirname(__file__), "Instruction.txt")
    try:
        with open(file_path, mode='r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f"警告：找不到指令文件 {file_path}")
        return ""


def process_query(query):
    """
    处理用户输入，识别意图并转换指令
    :param query: 用户输入的口语化内容
    :return: (is_instruction, result)
             - is_instruction: True表示是指令类，False表示是闲谈类
             - result: 标准指令 或 聊天回复
    """
    if not query or not query.strip():
        return False, "请说出您的指令或问题"
    
    standard_instruction = load_instruction_file()
    
    prompt = f"""
    你是一名指令标准化转化与意图识别助手，核心任务是：首先识别用户输入内容的类型（指令类或闲谈类），若为指令类，需根据用户提供的「口语化指令」和「标准指令示范文本」，提取口语化指令的核心意图、操作对象、关键参数（如文件路径、字段名、处理规则、输出要求等），参考示范文本的语法结构、术语规范和逻辑格式，剔除口语化词汇（如"帮我""大概""一下""哦"等），转化为无歧义、结构化、可被程序直接识别或映射为代码逻辑的标准指令；若为闲谈类，则生成符合智能助手身份的自然语言回应。

### 处理规则
1. 意图识别规则：
   - 指令类：内容包含明确的操作需求（如系统信息查询、程序控制、手机控制、播放视频、搜索商品、发消息等）、操作对象（如时间、程序名称、手机应用、视频名称、商品名称、联系人等）；
   - 闲谈类：内容为非操作类的问题、闲聊或陈述（如询问信息、日常对话、知识问答等）。
2. 指令转化规则（仅针对指令类内容）：
   - 精准匹配核心需求：不得遗漏口语化指令中的关键操作、操作对象、约束条件；
   - 严格遵循示范规范：参考示范文本的术语和句式结构；
   - 标准化表述：使用精准的指令术语，避免模糊表述；
   - 保留关键参数：如视频名称、商品名称、联系人、消息内容等必须保留。

### 输出要求
仅输出JSON格式结果，无需额外解释，JSON包含2个key：「standard_instruction」和「talk_text」。其中：
- 若为指令类内容，「standard_instruction」值为转化后的标准指令，「talk_text」值为空字符串；
- 若为闲谈类内容，「standard_instruction」值为空字符串，「talk_text」值为生成的回应内容。

### 示例
#### 示例输入1（指令类）
- 输入内容："帮我打开一下记事本软件"

#### 示例输出1
{{"standard_instruction": "打开记事本", "talk_text": ""}}

#### 示例输入2（指令类-带参数）
- 输入内容："帮我在B站上找个猫咪视频看看"

#### 示例输出2
{{"standard_instruction": "打开B站播放猫咪视频", "talk_text": ""}}

#### 示例输入3（指令类-微信消息）
- 输入内容："用微信告诉老妈我今晚回家吃饭"

#### 示例输出3
{{"standard_instruction": "打开微信发我今晚回家吃饭信息给老妈", "talk_text": ""}}

#### 示例输入4（闲谈类）
- 输入内容："你好，今天天气怎么样？"

#### 示例输出4
{{"standard_instruction": "", "talk_text": "你好！我是你的智能语音助手，不过我暂时无法查询天气信息。我可以帮你控制电脑程序、手机应用、播放视频、搜索商品等，有什么需要帮忙的吗？"}}

### 需要处理的内容
<query>
{query}
</query>

### 标准指令示范文本参考
<standard_instruction>
{standard_instruction}
</standard_instruction>
"""

    try:
        client = OpenAI(
            api_key=API_KEY,
            base_url=BASE_URL
        )
        
        completion = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "严格按照用户提供的输出要求，仅输出JSON格式结果，无需任何额外解释或修饰"},
                {"role": "user", "content": prompt}
            ],
            stream=False,
            extra_body={
                "enable_search": False,
                "enable_thinking": False
            },
            temperature=0.1
        )
        
        # 解析返回结果
        result_text = completion.choices[0].message.content.strip()
        
        # 尝试提取JSON（处理可能的markdown代码块）
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0].strip()
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0].strip()
        
        result_json = json.loads(result_text)
        
        standard_inst = result_json.get("standard_instruction", "").strip()
        talk_text = result_json.get("talk_text", "").strip()
        
        if standard_inst:
            return True, standard_inst
        else:
            return False, talk_text if talk_text else "我不太理解你的意思，请再说一遍"
    
    except json.JSONDecodeError as e:
        print(f"JSON解析错误: {e}, 原始内容: {result_text}")
        # 如果JSON解析失败，直接返回原始查询作为指令
        return True, query
    
    except Exception as e:
        print(f"LLM处理错误: {e}")
        # 出错时直接返回原始查询
        return True, query


def chat(query):
    """
    纯聊天对话（不进行指令转换）
    :param query: 用户输入
    :return: 回复内容
    """
    try:
        client = OpenAI(
            api_key=API_KEY,
            base_url=BASE_URL
        )
        
        completion = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "你是一个友好的智能语音助手，请用简洁的中文回答用户问题。回答要简短，适合语音播报。"},
                {"role": "user", "content": query}
            ],
            stream=False,
            temperature=0.7
        )
        
        return completion.choices[0].message.content.strip()
    
    except Exception as e:
        return f"抱歉，我遇到了一些问题：{str(e)}"


if __name__ == "__main__":
    # 测试
    test_queries = [
        "帮我打开一下记事本",
        "去B站找个搞笑视频看看",
        "用微信跟老妈说我今晚加班",
        "你叫什么名字？",
        "今天天气怎么样"
    ]
    
    for q in test_queries:
        print(f"\n输入: {q}")
        is_inst, result = process_query(q)
        if is_inst:
            print(f"类型: 指令类")
            print(f"标准指令: {result}")
        else:
            print(f"类型: 闲谈类")
            print(f"回复: {result}")
