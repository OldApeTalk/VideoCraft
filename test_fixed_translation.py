import os
import srt
import google.generativeai as genai

# 测试修复后的翻译逻辑
def test_fixed_translation():
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

    # 模拟完整的翻译流程
    batch_size = 30
    translated_subs = {}

    # 处理第2批（31-44号字幕，索引30-43）
    batch_start_idx = 30
    batch_contents = []
    for i in range(batch_start_idx, min(batch_start_idx + 14, len(subs))):
        batch_contents.append(f"{i+1}. {subs[i].content}")

    print(f"第2批包含 {len(batch_contents)} 条字幕 (全局索引 {batch_start_idx}-{batch_start_idx+len(batch_contents)-1})")

    # 创建输入
    numbered_input = '\n\n'.join(batch_contents)

    prompt = f"""You are a professional SRT subtitle translator. Your task is to translate the following SRT subtitles from English to Chinese.

The subtitles are provided in numbered format (31. subtitle, 32. subtitle, etc.). You must return the translated subtitles in the EXACT SAME numbered format.

CRITICAL REQUIREMENTS:
1. Translate EACH AND EVERY subtitle individually and separately
2. Return the EXACT SAME NUMBER of subtitles as input ({len(batch_contents)} subtitles)
3. Maintain the numbered format: "31. translated text", "32. translated text", etc.
4. DO NOT split any single subtitle into multiple subtitles
5. DO NOT merge multiple subtitles into one subtitle
6. DO NOT change the numbering or add/remove any subtitles
7. Preserve the original line breaks and formatting within each subtitle
8. Output ONLY the numbered subtitles, no explanations, comments, or additional text
9. Do NOT add quotation marks around translated text unless they are part of the original meaning
10. Ensure translation quality and natural language

Input subtitles ({len(batch_contents)} subtitles):
{numbered_input}

Return the translated subtitles in the same numbered format with {len(batch_contents)} subtitles:"""

    print("发送API请求...")
    response = model.generate_content(prompt)
    translated_batch = response.text.strip()

    print("API响应:")
    print(translated_batch[:300] + "..." if len(translated_batch) > 300 else translated_batch)

    # 模拟修复后的解析逻辑
    import re
    lines = translated_batch.split('\n')
    parsed_subs = {}

    current_num = None
    current_content = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        match = re.match(r'^(\d+)\.\s*(.*)$', line)
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
    print(f"parsed_subs 键: {list(parsed_subs.keys())}")

    # 模拟修复后的应用逻辑
    actual_size = len(batch_contents)
    for i in range(actual_size):
        global_idx = batch_start_idx + i
        if global_idx in parsed_subs:  # 修复：使用全局索引
            translated_content = parsed_subs[global_idx]
            translated_subs[global_idx] = translated_content
            print(f"✓ 字幕 {global_idx+1} (全局索引 {global_idx}): {translated_content[:50]}...")
        else:
            print(f"✗ 字幕 {global_idx+1} (全局索引 {global_idx}): 未找到翻译")

    print(f"\n最终结果: {len(translated_subs)}/{len(batch_contents)} 条字幕被翻译")

    # 应用到字幕对象
    untranslated_count = 0
    for i, sub in enumerate(subs):
        if i in translated_subs:
            sub.content = translated_subs[i]
            print(f"应用翻译: 字幕 {i+1}")
        else:
            untranslated_count += 1

    print(f"未翻译字幕数: {untranslated_count}")

    # 保存测试结果
    output_file = "test_fixed_translation.srt"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(srt.compose(subs))

    print(f"测试结果已保存到 {output_file}")

if __name__ == "__main__":
    test_fixed_translation()