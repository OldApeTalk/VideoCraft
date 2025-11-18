# Gemini-TTS 迁移完成

## ✅ 迁移内容

### 1. SDK 更新
- 升级 `google-cloud-texttospeech` 至 v2.33.0（支持 Gemini-TTS）
- 保持认证方式不变（Service Account JSON）

### 2. 模型更新
**旧版模型**：
- Standard（标准）
- Wavenet（高质量）
- Neural2（神经网络）
- Studio（工作室）

**新版 Gemini-TTS 模型**：
- `gemini-2.5-flash-tts` （推荐）- 低延迟，成本优化
- `gemini-2.5-pro-tts` （高质量）- 最高质量输出
- `gemini-2.5-flash-lite-tts` （快速）- 最快响应

### 3. 语音更新
**旧版语音**：基于语言和模型的组合（如 `cmn-CN-Wavenet-A`）

**新版 Gemini-TTS 语音**（40+ 通用语音，支持多语言）：
- **女声**：Kore, Aoede, Autonoe, Callirrhoe, Despina, Erinome, Gacrux, Laomedeia, Leda, Pulcherrima, Sulafat, Vindemiatrix, Zephyr
- **男声**：Charon, Achird, Algenib, Algieba, Alnilam, Enceladus, Fenrir, Iapetus, Orus, Puck, Rasalgethi, Sadachbia, Sadaltager, Schedar, Umbriel, Zubenelgenubi

### 4. 新增功能：Style Prompt ✨

Gemini-TTS 支持自然语言控制语音风格：

#### 预设风格：
- **自然朗读**："用自然、流畅的语气朗读"
- **温暖友好**："用温暖、友好的语气讲述"
- **专业播报**："用专业、清晰的语气播报"
- **平静叙述**："用平静、舒缓的语气叙述"
- **兴奋激昂**："用兴奋、充满活力的语气表达"
- **新闻播报**："用新闻播音员的专业语气播报"
- **故事讲述**："用生动、富有表现力的语气讲故事"

#### 标记语法：
- `[whispering]` - 耳语
- `[laughing]` - 笑声
- `[sigh]` - 叹气
- `[extremely fast]` - 极快速度
- `[short pause]` - 短暂停顿
- `[medium pause]` - 中等停顿
- `[long pause]` - 长时间停顿

### 5. 保留功能
以下传统参数全部保留：
- ✅ 语速（speaking_rate）：0.25x - 4.0x
- ✅ 音调（pitch）：-20.0 - 20.0
- ✅ 音量增益（volume_gain_db）：-96.0 - 16.0 dB
- ✅ 音频格式：MP3, WAV, OGG_OPUS

## 🎯 使用方法

### 基础使用（与旧版相同）
1. 确保配置了 Google Cloud 服务账户密钥
2. 选择语言（如：cmn-CN 普通话）
3. 选择 Gemini 模型（推荐：gemini-2.5-flash-tts）
4. 选择语音（如：Kore 或 Charon）
5. 输入文本，点击"生成语音"

### 高级使用（新功能）
1. **使用预设风格**：
   - 点击"预设风格▼"按钮
   - 选择合适的风格（如"温暖友好"）
   
2. **自定义 Prompt**：
   - 在 Prompt 输入框中输入自然语言描述
   - 例如："用激动的语气，像在宣布重大新闻一样"
   
3. **使用标记语法**：
   - 在文本中插入标记
   - 例如："这真是太棒了[laughing]，我简直不敢相信！"

## 🔧 技术细节

### API 调用变化

**旧版 API**：
```python
voice = texttospeech.VoiceSelectionParams(
    language_code="cmn-CN",
    name="cmn-CN-Wavenet-A"
)
synthesis_input = texttospeech.SynthesisInput(text=text)
```

**新版 Gemini-TTS API**：
```python
voice = texttospeech.VoiceSelectionParams(
    language_code="cmn-CN",
    name="Kore",
    model_name="gemini-2.5-flash-tts"  # 必须指定
)
synthesis_input = texttospeech.SynthesisInput(
    text=text,
    prompt="用温暖、自然的语气朗读"  # 可选
)
```

### 配置文件不变
- 位置：`keys/google_cloud_config.json`
- 格式：Service Account JSON 或指向密钥文件的配置
- 环境变量：`GOOGLE_APPLICATION_CREDENTIALS`

## 📊 测试状态

- ✅ SDK 升级完成（v2.33.0）
- ✅ UI 更新完成
- ✅ 模型选择更新
- ✅ 语音列表更新
- ✅ Prompt 功能添加
- ✅ 预设风格菜单
- ✅ API 调用更新
- ✅ 程序成功启动

## ⚠️ 注意事项

1. **中文支持**：
   - 语言码：`cmn-CN`（Mandarin China）
   - 当前处于 Preview 阶段，建议实际测试效果

2. **认证方式**：
   - 无需改变，继续使用 Service Account JSON
   - 不需要申请新的 API Key

3. **兼容性**：
   - Gemini-TTS 不向后兼容旧版语音名称
   - 旧版配置需要重新选择语音

4. **定价**：
   - Gemini-TTS 可能有不同的定价
   - 建议查看 [Google Cloud 定价页面](https://cloud.google.com/text-to-speech/pricing)

## 🚀 下一步

Phase 2（可选）：
- [ ] 添加语音预览功能
- [ ] 实现流式合成（实时应用）
- [ ] 多说话人对话生成

## 📚 参考文档

- [Gemini-TTS 官方文档](https://cloud.google.com/text-to-speech/docs/gemini-tts)
- [可用语音列表](https://cloud.google.com/text-to-speech/docs/gemini-tts#voice_options)
- [支持的语言](https://cloud.google.com/text-to-speech/docs/gemini-tts#available_languages)
- [Prompt 技巧](https://cloud.google.com/text-to-speech/docs/gemini-tts#prompting_tips)
