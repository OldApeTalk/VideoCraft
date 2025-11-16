import os
import srt
import google.generativeai as genai

# 测试新的醒目标记格式
def test_bracket_format():
    # 读取 Gemini API Key
    if not os.path.exists('Gemini.key'):
        print("请先配置Gemini Key")
        return

    with open('Gemini.key', 'r') as f:
        api_key = f.read().strip()
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.5-flash-lite")

    # 读取测试字幕文件
    test_srt_path = r"d:\My_新闻短片\20251115\米歇尔巴赫曼的演讲\English.srt"
    if not os.path.exists(test_srt_path):
        print(f"测试文件不存在: {test_srt_path}")
        return

    with open(test_srt_path, 'r', encoding='utf-8') as f:
        subs = list(srt.parse(f))

    print(f"读取到 {len(subs)} 条字幕")

    # 测试第2批（31-44号字幕，索引30-43）
    batch_start_idx = 30
    batch_contents = []
    for i in range(batch_start_idx, min(batch_start_idx + 14, len(subs))):
        # 使用新的醒目标记格式
        batch_contents.append(f"【{i+1}】{subs[i].content}")

    print(f"第2批包含 {len(batch_contents)} 条字幕 (全局索引 {batch_start_idx}-{batch_start_idx+len(batch_contents)-1})")

    # 创建输入
    numbered_input = '\n\n'.join(batch_contents)

    prompt = f"""You are a professional SRT subtitle translator. Your task is to translate the following SRT subtitles from English to Chinese.

The subtitles are provided in a special numbered format with 【number】 markers (【31】subtitle, 【32】subtitle, etc.). You must return the translated subtitles in the EXACT SAME special numbered format.

CRITICAL REQUIREMENTS:
1. Translate EACH AND EVERY subtitle individually and separately
2. Return the EXACT SAME NUMBER of subtitles as input ({len(batch_contents)} subtitles)
3. Maintain the special numbered format: "【31】translated text", "【32】translated text", etc.
4. DO NOT split any single subtitle into multiple subtitles
5. DO NOT merge multiple subtitles into one subtitle
6. DO NOT change the numbering or add/remove any subtitles
7. DO NOT remove the 【】markers - they are essential for identification
8. Preserve the original line breaks and formatting within each subtitle
9. Output ONLY the numbered subtitles with 【】markers, no explanations, comments, or additional text
10. Do NOT add quotation marks around translated text unless they are part of the original meaning
11. Ensure translation quality and natural language

Input subtitles ({len(batch_contents)} subtitles):
{numbered_input}

Return the translated subtitles in the same special 【number】 format with {len(batch_contents)} subtitles:"""

    print("发送API请求...")
    response = model.generate_content(prompt)
    translated_batch = response.text.strip()

    print("API响应:")
    print(translated_batch[:500] + "..." if len(translated_batch) > 500 else translated_batch)

    # 测试新的解析逻辑
    import re
    lines = translated_batch.split('\n')
    parsed_subs = {}

    current_num = None
    current_content = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # 使用新的正则表达式匹配【数字】格式
        match = re.match(r'^【(\d+)】\s*(.*)$', line)
        if match:
            if current_num is not None and current_content:
                parsed_subs[current_num] = '\n'.join(current_content).strip()

            current_num = int(match.group(1)) - 1  # 转换为0-based索引
            current_content = [match.group(2)]
        elif current_num is not None:
            current_content.append(line)

    if current_num is not None and current_content:
        parsed_subs[current_num] = '\n'.join(current_content).strip()

    print(f"解析结果: 找到 {len(parsed_subs)} 条翻译")
    print(f"parsed_subs 键: {sorted(list(parsed_subs.keys()))}")

    # 测试应用逻辑
    translated_subs = {}
    actual_size = len(batch_contents)
    for i in range(actual_size):
        global_idx = batch_start_idx + i
        if global_idx in parsed_subs:
            translated_content = parsed_subs[global_idx]
            translated_subs[global_idx] = translated_content
            print(f"✓ 字幕 {global_idx+1} (全局索引 {global_idx}): {translated_content[:50]}...")
        else:
            print(f"✗ 字幕 {global_idx+1} (全局索引 {global_idx}): 未找到翻译")

    print(f"\n最终结果: {len(translated_subs)}/{len(batch_contents)} 条字幕被翻译")

    # 保存测试结果
    with open('test_bracket_format.txt', 'w', encoding='utf-8') as f:
        f.write("=== 输入格式 ===\n")
        f.write(numbered_input)
        f.write("\n\n=== API 响应 ===\n")
        f.write(translated_batch)
        f.write("\n\n=== 解析结果 ===\n")
        for idx, content in sorted(parsed_subs.items()):
            f.write(f"字幕 {idx+1}: {content}\n")

    print("测试结果已保存到 test_bracket_format.txt")

if __name__ == "__main__":
    test_bracket_format()