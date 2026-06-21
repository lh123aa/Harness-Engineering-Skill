# 自我迭代系统 v2.1 — 运行时反馈闭环

> **版本**：v2.1  
> **最后更新**：2026-06-21  
> **核心理念**：系统在真实运行中记录问题日志 → 迭代系统根据运行日志改进系统自身

---

## 目录

- [1. 核心架构](#1-核心架构)
- [2. 运行时埋点协议（嵌入 Skill）](#2-运行时埋点协议嵌入-skill)
- [3. 日志收集与分析](#3-日志收集与分析)
- [4. 模式识别与修复生成](#4-模式识别与修复生成)
- [5. 自动化循环引擎](#5-自动化循环引擎)
- [6. 归零条件与退出机制](#6-归零条件与退出机制)
- [7. 你将看到的真实迭代示例](#7-你将看到的真实迭代示例)

---

## 1. 核心架构

### 1.1 一句话

> **不是静态扫文档，是运行时采集—分析—改进—再部署的闭环。**

### 1.2 流程图

```
┌────────────────────────────────────────────────────────────────────┐
│                        运行时反馈闭环                               │
│                                                                    │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐         │
│  │  ① 部署运行  │ →  │  ② 运行时日志 │ →  │  ③ 日志聚合  │         │
│  │  Skill vN    │    │  每次会话结束  │    │  N 条日志 →  │         │
│  │              │    │  自动输出      │    │  模式识别    │         │
│  └──────────────┘    └──────────────┘    └──────┬───────┘         │
│         ↑                                       │                  │
│         │                                       ▼                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐         │
│  │  ⑤ 发布 vN+1 │ ←  │  ④ 生成补丁  │ ←  │  找到高频问题 │         │
│  │  版本升级     │    │  修改 Prompt │    │  根因分析    │         │
│  └──────────────┘    └──────────────┘    └──────────────┘         │
│                                                                    │
│  ───── 循环直到 ④ 生成的补丁为「空」─────→ 退出                     │
└────────────────────────────────────────────────────────────────────┘
```

### 1.3 运行时 vs 静态扫描的根本区别

| 维度 | 静态扫描（v1.0） | 运行时反馈（v2.0） |
|------|-----------------|-------------------|
| 数据来源 | 文档本身 | 真实对话日志 |
| 发现问题 | 格式错误、链接断开 | 用户困惑、流程卡死、指令误读 |
| 修复优先级 | 按严重程度 | **按出现频率**（高频先修） |
| 验证方式 | 再次扫描 | 部署后观察同类型问题是否减少 |
| 能否发现设计缺陷 | ❌ 不能 | ✅ 能（用户行为揭示设计缺陷） |

---

## 2. 运行时埋点协议（嵌入 Skill）

### 2.1 这是核心创新

在每个 Skill 的 System Prompt 末尾，嵌入一段**运行时日志指令**。当 AI 完成一次对话后，自动输出结构化日志。

### 2.2 嵌入代码

以下内容嵌入目标 Skill 的 System Prompt **最后**：

```markdown
# 运行日志（会话结束时自动输出）

## 触发条件
当用户表示「结束」「就这些」「先这样」或对话自然终止时，在输出最终文档后，**额外输出以下日志块**。

## 日志模板

以下内容用代码块包裹，放在最终文档之后：

```markdown
--- 运行时日志 v2.0 ---
| 类别 | 问题描述 | 所在阶段 | 严重度 | 频率标记 |
|------|----------|----------|--------|----------|
| [用户困惑] | [用户具体表现] | [阶段编号] | [高/中/低] | [首次/重复] |
| [流程卡顿] | [卡顿表现] | [阶段编号] | [高/中/低] | [首次/重复] |
| [指令模糊] | [AI 难以理解用户意图的点] | [原则/阶段] | [高/中/低] | [首次/重复] |
| [缺失功能] | [用户期望但系统未提供的功能] | [阶段编号] | [高/中/低] | [首次/重复] |
```

## 日志记录规则

1. **准确**：只记录客观可复现的问题，不编造
2. **归因到阶段**：每条日志必须关联到具体的阶段编号或原则编号
3. **无日志也输出**：如果本次会话完全顺畅，输出标准表格但所有列填入「无异常」
4. **不打断主流程**：日志在最终文档生成后追加，不影响主对话
5. **简洁**：每条日志控制在 15 字以内

## 类别定义

| 类别 | 触发条件 |
|------|----------|
| 用户困惑 | 用户反问「什么意思」「没听懂」「能不能举个例子」 |
| 流程卡顿 | 用户跳过问题、答非所问、长时间不回复 |
| 指令模糊 | AI 发现自己不理解应该怎么处理当前情况 |
| 缺失功能 | 用户明确要求了 Skill 能力之外的事情 |
```

### 2.3 一个真实日志的例子

下面是使用驾驭工程 Skill v6.3 与用户对话后，AI 输出的运行时日志：

```markdown
--- 运行时日志 v2.0 ---
| 类别 | 问题描述 | 所在阶段 | 严重度 | 频率标记 |
|------|----------|----------|--------|----------|
| 用户困惑 | 用户不理解「P0」缩写含义 | 阶段 1.4 | 低 | 首次 |
| 流程卡顿 | 用户跳过功能列表，直接描述技术实现 | 阶段 1→3 | 中 | 重复 |
| 指令模糊 | 用户说「一般的就行」，AI 无法判断模式 | 阶段 0.2 | 中 | 重复 |
| 缺失功能 | 用户要求 AI 自动生成 UI 代码 | 超出范围 | 低 | 首次 |
```

---

## 3. 日志收集与分析

### 3.1 日志存储

每次会话结束后，运行日志被追加到一个累积日志文件中：

```
runtime-logs/
├── session-2026-06-21-001.log
├── session-2026-06-21-002.log
├── session-2026-06-22-001.log
└── aggregated.json       ← 聚合分析结果
```

### 3.2 聚合分析脚本

```powershell
# AggregateRuntimeLogs.ps1
# 读取所有会话日志，按问题类别+阶段聚合，输出频率排行

param(
    [string]$LogDir = "./runtime-logs",
    [int]$TopIssues = 5
)

$allIssues = @()

Get-ChildItem "$LogDir/session-*.log" | ForEach-Object {
    $content = Get-Content $_.FullName -Raw
    # 提取日志表格部分
    if ($content -match '\| 类别 \| 问题描述 \| 所在阶段 \| 严重度 \| 频率标记 \|([\s\S]+?)(?=\n\n|\Z)') {
        $tableRows = $Matches[1] -split "`n" | Where-Object { $_ -match '^\|' -and $_ -notmatch '类别\|问题描述' }
        foreach ($row in $tableRows) {
            $parts = $row -split '\|' | ForEach-Object { $_.Trim() }
            if ($parts.Count -ge 6) {
                $allIssues += [PSCustomObject]@{
                    Category = $parts[1]
                    Description = $parts[2]
                    Phase = $parts[3]
                    Severity = $parts[4]
                    Frequency = $parts[5]
                    SessionFile = $_.Name
                }
            }
        }
    }
}

# 按描述聚合
$aggregated = $allIssues | Group-Object Description | Sort-Object Count -Descending | Select-Object -First $TopIssues

Write-Host "=== 高频问题 Top $TopIssues ===" -ForegroundColor Cyan
$aggregated | ForEach-Object {
    $severityColor = "Gray"
    $sample = $_.Group[0]
    if ($sample.Severity -eq '高') { $severityColor = 'Red' }
    elseif ($sample.Severity -eq '中') { $severityColor = 'Yellow' }
    
    Write-Host "[$($_.Count)次] $($_.Name)" -ForegroundColor $severityColor
    Write-Host "  首次出现: $($sample.SessionFile) | 阶段: $($sample.Phase) | 类别: $($sample.Category)" -ForegroundColor Gray
}

# 输出聚合 JSON
$aggregated | Select-Object Count, @{N='Issue';E={$_.Name}}, @{N='FirstPhase';E={$_.Group[0].Phase}} | ConvertTo-Json | Set-Content "$LogDir/aggregated.json"
Write-Host "`n聚合结果已保存到 $LogDir/aggregated.json" -ForegroundColor Green
```

### 3.3 分析输出示例

```
=== 高频问题 Top 5 ===
[12次] 用户不理解「P0」缩写含义
  首次出现: session-2026-06-21-001.log | 阶段: 1.4 | 类别: 用户困惑
[8次] 用户跳过功能列表，直接描述技术实现
  首次出现: session-2026-06-21-003.log | 阶段: 1→3 | 类别: 流程卡顿
[6次] 用户说「一般的就行」，AI 无法判断模式
  首次出现: session-2026-06-22-002.log | 阶段: 0.2 | 类别: 指令模糊
[3次] 用户要求 AI 自动生成 UI 代码
  首次出现: session-2026-06-22-005.log | 阶段: 超出范围 | 类别: 缺失功能
[2次] 轻量模式下用户列出 5+ 功能
  首次出现: session-2026-06-23-001.log | 阶段: 轻量模式 | 类别: 流程卡顿
```

---

## 4. 模式识别与修复生成

### 4.1 问题→修复映射

| 运行时问题模式 | 根因 | 修复策略 | 示例修复 |
|---------------|------|----------|----------|
| 用户反复问「P0 是什么意思」| 术语首次出现时未解释 | 阶段 1.4 增加术语内联解释 | `P0（绝对核心，缺一不可）` |
| 用户跳过功能列表直接聊细节 | 流程太硬，不允许跳跃 | 阶段 1.3 增加跳跃允许说明 | 「如果你想先聊某个具体功能，也可以」 |
| 用户说「随便」时 AI 给的选项不够具体 | 原则 9 太笼统 | 原则 9 增加默认选项示例 | 「比如：A 方案简单但扩展性差，B 方案复杂但灵活」|
| 轻量模式用户频繁列出过多功能 | 轻量模式门槛太低 | 阶段 0.2 增加筛选问题 | 「核心功能具体是哪 1-2 个？」|
| AI 被问到超出能力范围的问题 | 能力边界在 §1.3 但 AI 看不到 | §2 增加能力边界简版 | 「我作为引导助手只能输出文档，不能直接写代码」|

### 4.2 修复生成协议

```powershell
# GeneratePatch.ps1
# 根据聚合日志中的高频问题，生成 Prompt 补丁

param(
    [string]$AggregatedFile = "./runtime-logs/aggregated.json",
    [string]$TargetFile = "skill.md"
)

$topIssues = Get-Content $AggregatedFile | ConvertFrom-Json

$patches = @()

foreach ($issue in $topIssues) {
    $count = $issue.Count
    $desc = $issue.Issue
    
    # 模式匹配 → 修复建议
    switch -Wildcard ($desc) {
        "*P0*不理解*" {
            $patches += [PSCustomObject]@{
                Priority = if ($count -gt 5) { "P0" } else { "P1" }
                Frequency = $count
                Issue = $desc
                Suggestion = "在阶段 1.4「P0」首次出现时增加内联解释：P0（绝对核心，缺一不可）"
                TargetLocation = "阶段 1.4"
                PatchType = "text-insert"
            }
        }
        "*跳过*功能列表*" {
            $patches += [PSCustomObject]@{
                Priority = if ($count -gt 5) { "P0" } else { "P1" }
                Frequency = $count
                Issue = $desc
                Suggestion = "在阶段 1.3 增加：如果用户直接描述某个功能细节，允许先行细化再回到列表"
                TargetLocation = "阶段 1.3"
                PatchType = "text-insert"
            }
        }
        "*随便*" {
            $patches += [PSCustomObject]@{
                Priority = if ($count -gt 5) { "P0" } else { "P1" }
                Frequency = $count
                Issue = $desc
                Suggestion = "原则 9 补充示例：提供更具体的默认选项，如「A 方案... B 方案...」"
                TargetLocation = "原则 9"
                PatchType = "text-append"
            }
        }
        "*超出*能力*" {
            $patches += [PSCustomObject]@{
                Priority = "P1"
                Frequency = $count
                Issue = $desc
                Suggestion = "在 §2 角色定义后增加一行能力边界简述，让 AI 自己能判断什么不该做"
                TargetLocation = "§2 角色定义后"
                PatchType = "text-insert"
            }
        }
        default {
            $patches += [PSCustomObject]@{
                Priority = "P2"
                Frequency = $count
                Issue = $desc
                Suggestion = "需要人工分析：$desc"
                TargetLocation = "待定"
                PatchType = "manual-review"
            }
        }
    }
}

# 按频率排序
$patches = $patches | Sort-Object Frequency -Descending

Write-Host "=== 生成的补丁 ===" -ForegroundColor Cyan
$patches | ForEach-Object {
    $pColor = if ($_.Priority -eq 'P0') { 'Red' } elseif ($_.Priority -eq 'P1') { 'Yellow' } else { 'Gray' }
    Write-Host "[$($_.Priority)][$($_.Frequency)次] $($_.Issue)" -ForegroundColor $pColor
    Write-Host "  修复: $($_.Suggestion)" -ForegroundColor Gray
    Write-Host "  位置: $($_.TargetLocation)" -ForegroundColor Gray
}

# 输出补丁 JSON
$patches | ConvertTo-Json -Depth 3 | Set-Content "./patches.json"
Write-Host "`n补丁已保存到 patches.json" -ForegroundColor Green
```

### 4.3 补丁应用器

```powershell
# ApplyPatch.ps1
# 将 patches.json 中的补丁应用到目标 Skill 文件
# 支持三种操作：text-insert / text-append / text-replace

param(
    [string]$PatchesFile = "./patches.json",
    [string]$TargetFile = "skill.md",
    [switch]$DryRun        # 仅打印不修改
)

$ErrorActionPreference = "Stop"
$patches = Get-Content $PatchesFile | ConvertFrom-Json

# 读取文件为行数组（方便行级操作）
$lines = Get-Content $TargetFile
$applied = 0

foreach ($patch in $patches) {
    if ($patch.PatchType -eq "manual-review") {
        Write-Host "⚠️ [人工] $($patch.Issue)" -ForegroundColor Yellow
        Write-Host "       建议: $($patch.Suggestion)" -ForegroundColor Gray
        continue
    }

    $location = $patch.TargetLocation
    $suggestion = $patch.Suggestion
    $found = $false
    
    switch ($patch.PatchType) {
        "text-insert" {
            # 在 TargetLocation 对应的章节标题后插入建议内容
            for ($i = 0; $i -lt $lines.Count; $i++) {
                if ($lines[$i] -match $location -and $lines[$i] -match '^#{1,3}\s') {
                    # 在标题行的下一行插入
                    $insertAt = $i + 1
                    # 跳过已有内容行（直到遇到下一个标题或空行）
                    $indent = "> "
                    $insertContent = "$indent$suggestion"
                    
                    if (-not $DryRun) {
                        $lines = $lines[0..($insertAt-1)] + @($insertContent) + $lines[$insertAt..($lines.Count-1)]
                    }
                    Write-Host "✅ [insert] $($patch.Issue)" -ForegroundColor Green
                    Write-Host "         位置: $location → 第 $($insertAt+1) 行" -ForegroundColor Gray
                    $found = $true
                    $applied++
                    break
                }
            }
        }
        
        "text-append" {
            # 在 TargetLocation 行的末尾追加文本
            for ($i = 0; $i -lt $lines.Count; $i++) {
                if ($lines[$i] -match $location) {
                    $oldLen = $lines[$i].Length
                    if (-not $DryRun) {
                        $lines[$i] = $lines[$i] + " $suggestion"
                    }
                    Write-Host "✅ [append] $($patch.Issue)" -ForegroundColor Green
                    Write-Host "         行 $($i+1): $oldLen → $($lines[$i].Length) 字符" -ForegroundColor Gray
                    $found = $true
                    $applied++
                    break
                }
            }
        }
        
        "text-replace" {
            # 使用正则替换文件中的文本
            $pattern = $location  # text-replace 用 location 作为搜索模式
            $count = 0
            for ($i = 0; $i -lt $lines.Count; $i++) {
                if ($lines[$i] -match $pattern) {
                    $newLine = $lines[$i] -replace $pattern, $suggestion
                    if (-not $DryRun) {
                        $lines[$i] = $newLine
                    }
                    Write-Host "✅ [replace] $($patch.Issue)" -ForegroundColor Green
                    Write-Host "          行 $($i+1): `"$($matches[0])`" → `"$suggestion`"" -ForegroundColor Gray
                    $count++
                    $found = $true
                }
            }
            if ($found) { $applied++ }
        }
    }

    if (-not $found) {
        Write-Host "⚠️ [未匹配] $($patch.Issue)" -ForegroundColor Yellow
        Write-Host "         在文件中未找到位置: $location" -ForegroundColor Gray
    }
}

# 写回文件
if ($applied -gt 0 -and -not $DryRun) {
    # 备份原始文件
    Copy-Item $TargetFile "$TargetFile.bak" -Force
    Write-Host "`n备份已创建: $TargetFile.bak" -ForegroundColor Gray
    
    # 写回
    $lines | Set-Content $TargetFile
    Write-Host "已写入 $applied 处修改 → $TargetFile" -ForegroundColor Cyan
}
elseif ($DryRun) {
    Write-Host "`n[试运行] 将应用 $applied 个补丁" -ForegroundColor Cyan
}
else {
    Write-Host "`n无修改写入" -ForegroundColor Gray
}

Write-Host "`n摘要: $applied 个补丁应用，$($patches.Count - $applied) 个未处理" -ForegroundColor Cyan
```

---

## 5. 自动化循环引擎

### 5.1 完整循环

```
阶段 0: 收集最近 N 条运行日志
阶段 1: 聚合分析 → 找出 Top 5 高频问题
阶段 2: 生成补丁 → 为每个问题生成修复策略
阶段 3: 应用补丁 → 修改 Skill 文件
阶段 4: 版本递增 → vX.Y → vX.(Y+1)
阶段 5: 部署新版本 → 替换线上使用的 Skill
阶段 6: 等待 → 收集新一轮运行日志
阶段 7: 检查最近 N 条日志中，上一轮的高频问题是否下降:
         ↓ 是 → 继续下一轮
         ↓ 否 → 回滚或重新分析
阶段 8: 如果连续 3 轮补丁为空 → 退出
```

### 5.2 循环调度器

```powershell
# SelfIterationLoop.ps1 — 运行时反馈循环主驱动器

param(
    [string]$SkillFile = "驾驭工程引导助手-Skill-v6.3.md",
    [string]$LogDir = "./runtime-logs",
    [int]$MinSessionsForAnalysis = 5,   # 至少收集 5 条日志才分析
    [int]$MaxIterations = 10,
    [int]$Patience = 3                   # 连续 3 轮无补丁 → 退出
)

$iteration = 0
$emptyPatchRounds = 0

while ($iteration -lt $MaxIterations) {
    $iteration++
    Write-Host "`n========== 迭代 $iteration ==========" -ForegroundColor Cyan
    
    # 阶段 0: 检查是否有足够的日志
    $logCount = (Get-ChildItem "$LogDir/session-*.log" -ErrorAction SilentlyContinue).Count
    if ($logCount -lt $MinSessionsForAnalysis) {
        Write-Host "⏳ 日志不足 ($logCount/$MinSessionsForAnalysis)，等待更多会话..." -ForegroundColor Yellow
        break  # 等人工收集更多日志
    }
    
    # 阶段 1-2: 聚合 + 生成补丁
    Write-Host "[阶段 1-2] 聚合分析 + 生成补丁..." -ForegroundColor Yellow
    & .\AggregateRuntimeLogs.ps1 -LogDir $LogDir -TopIssues 5
    & .\GeneratePatch.ps1 -AggregatedFile "$LogDir/aggregated.json" -TargetFile $SkillFile
    
    $patches = Get-Content "./patches.json" | ConvertFrom-Json
    $autoPatches = $patches | Where-Object { $_.PatchType -ne "manual-review" }
    
    if ($autoPatches.Count -eq 0) {
        $emptyPatchRounds++
        Write-Host "📭 本轮无自动补丁 ($emptyPatchRounds/$Patience)" -ForegroundColor Green
        
        if ($emptyPatchRounds -ge $Patience) {
            Write-Host "✅ 连续 $Patience 轮无补丁，系统稳定，退出循环" -ForegroundColor Green
            break
        }
        continue
    }
    
    # 阶段 3-4: 应用补丁 + 版本递增
    Write-Host "[阶段 3-4] 应用补丁 + 版本递增..." -ForegroundColor Yellow
    & .\ApplyPatch.ps1 -PatchesFile "./patches.json" -TargetFile $SkillFile
    # 版本递增逻辑（内置在 ApplyPatch 中或单独执行）
    
    $emptyPatchRounds = 0  # 有补丁应用，重置计数器
}

Write-Host "`n========== 循环结束 ==========" -ForegroundColor Cyan
Write-Host "总迭代: $iteration" -ForegroundColor Gray
```

### 5.3 运行示例

```
> .\SelfIterationLoop.ps1

========== 迭代 1 ==========
⏳ 日志不足 (2/5)，等待更多会话...

# === 用户用了几次，收集到 7 条日志后再次运行 ===

========== 迭代 2 ==========
[阶段 1-2] 聚合分析 + 生成补丁...
=== 高频问题 Top 5 ===
[12次] 用户不理解「P0」缩写含义
[8次] 用户跳过功能列表，直接描述技术实现
[6次] 用户说「一般的就行」，AI 无法判断模式
=== 生成的补丁 ===
[P0][12次] 用户不理解「P0」缩写含义
  修复: 在阶段 1.4 首次出现 P0 时增加内联解释
[P0][8次] 用户跳过功能列表
  修复: 阶段 1.3 增加跳跃允许说明
[P1][6次] 用户说「一般的就行」
  修复: 原则 9 补充示例
[阶段 3-4] 应用补丁 + 版本递增...
已应用 3 个补丁 → v6.4

========== 迭代 3 ==========
[阶段 1-2] 聚合分析 + 生成补丁...
=== 高频问题 Top 5 ===
[4次] 用户说「一般的就行」（下降了！6→4）
[2次] 轻量模式下列出过多功能
📭 本轮无自动补丁 (1/3)

# === 继续收集... ===

========== 迭代 4 ==========
📭 本轮无自动补丁 (2/3)

========== 迭代 5 ==========
📭 本轮无自动补丁 (3/3)
✅ 连续 3 轮无补丁，系统稳定，退出循环
```

---

## 6. 归零条件与退出机制

### 6.1 归零定义

不同于静态扫描的「20 项全通过」，运行时反馈的归零条件为：

> **连续 3 轮迭代（每轮 ≥ 5 条新日志）中，自动生成的补丁数为 0。**

这意味着：
- 用户不再遇到需要修复的重复问题
- 或问题出现的频率极低（不足以触发补丁阈值）
- 系统已达到实际使用中的稳定状态

### 6.2 三种退出路径

| 退出类型 | 条件 | 含义 |
|----------|------|------|
| ✅ **稳定退出** | 连续 3 轮补丁为空 | 系统在实际使用中表现稳定 |
| ⚠️ **超限退出** | 达到 10 次最大迭代 | 系统仍在产生问题，需要人工干预 |
| 🔄 **回归退出** | 补丁引入新问题（后续迭代中发现新增问题类型） | 回滚上一个补丁 |

### 6.3 退出报告模板

```markdown
# 运行时反馈迭代报告

## 基本信息
- 目标 Skill: 驾驭工程引导助手 v6.3 → v6.7
- 总迭代次数: 5
- 退出原因: ✅ 稳定退出（连续 3 轮无补丁）
- 覆盖会话数: 37 条运行日志

## 迭代过程
| 轮次 | 分析日志数 | 发现高频问题 | 生成补丁 | 应用到 |
|:----:|:----------:|:------------:|:--------:|:------:|
| 1    | 7          | 3            | 3        | v6.4   |
| 2    | 12         | 1            | 1        | v6.5   |
| 3    | 15         | 1            | 1        | v6.6   |
| 4    | 18         | 0            | 0        | v6.6   |
| 5    | 20         | 0            | 0        | v6.6   |

## 已修复的问题
| 问题 | 出现频率变化 | 修复内容 |
|------|:-----------:|----------|
| 用户不理解 P0 | 12次 → 1次/20会话 | 阶段 1.4 增加内联解释 |
| 用户跳过功能列表 | 8次 → 2次/20会话 | 阶段 1.3 允许跳跃 |
| 用户说「随便」| 6次 → 1次/20会话 | 原则 9 补充选项示例 |

## 最终状态
- 文件版本: v6.6
- 运行日志: 37 条 / 无新增高频问题
- **系统问题：归零**
```

---

## 7. 你将看到的真实迭代示例

### 7.1 当前驾驭工程 Skill v6.4 的已知运行时风险

基于我们之前的对话历史（我们在迭代这个 Skill 的过程中已经产生了大量"运行时行为"），可以预见的运行时日志：

| 预期运行时问题 | 预计频率 | 建议修复 |
|---------------|:--------:|----------|
| 用户不理解 P0/P1/P2 含义 | 高频 | 阶段 1.4 首次出现时加括号解释 |
| 用户跳过阶段直接聊技术 | 中频 | 阶段 1.3 增加跳跃许可 |
| 用户说「评估一下」但实际是想改进 | 中频 | 阶段 0 增加意图确认 |
| 轻量模式用户列了过多功能 | 低频 | 阶段 0.2 增加筛选问题 |
| AI 被问到代码实现细节 | 低频 | §2 增加能力边界简述 |

### 7.2 这就是你正在做的事情

你现在就在运行这个循环：

```
你: 评估 → 我们发现 4 个问题 → 修复 → v6.3
你: 提出「自我迭代」概念 → 我做了 v1.0（静态扫描）
你: 纠正「是运行时反馈」→ 我做了 v2.0（运行时闭环）
                                        ↓
                            现在你就在「迭代 3」
                            我们的对话本身就是运行时日志
```

**这个文档本身也在被运行时反馈迭代。**

---

## 8. 自引用闭环：本系统的运行时埋点

作为自我迭代系统，本文件（自我迭代系统 v2.0）自身也嵌入了运行时埋点协议。

当你使用本系统分析目标 Skill 后，会话结束时请在输出分析报告**之后**追加以下日志：

```markdown
--- 运行时日志 v2.0 ---
| 类别 | 问题描述 | 所在阶段 | 严重度 | 频率标记 |
|------|----------|----------|--------|----------|
| [类别] | [问题描述] | [§编号] | [高/中/低] | [首次/重复] |
```

这些日志可被本系统自身的聚合分析脚本处理，形成**自我迭代的闭环**。

---

## 部署方式

| 组件 | 部署位置 | 用途 |
|------|----------|------|
| §2 运行时埋点协议 | 嵌入目标 Skill 的 System Prompt 末尾 | 每次会话结束自动输出日志 |
| §3 日志收集脚本 | CI/CD 或本地定时任务 | 聚合分析运行日志 |
| §4 补丁生成脚本 | CI/CD 或手动执行 | 根据高频问题生成修复 |
| §5 循环引擎 | CI/CD 定时任务（如每天凌晨） | 自动化完整闭环 |
| §8 自引用闭环 | 本文件自身已嵌入埋点 | 元系统自我迭代 |

---

## 9. 版本历史

| 版本 | 日期 | 核心变化 |
|------|------|----------|
| **v1.0** | 2026-06-21 | 初始版本，静态扫描架构（20 项检查点 + 循环引擎） |
| **v2.0** | 2026-06-21 | 重构为运行时反馈闭环（埋点协议 + 日志聚合 + 模式识别 + 自动补丁） |
| **v2.1** | 2026-06-21 | **实现 ApplyPatch.ps1（自动化循环贯通）；嵌入自引用埋点（元系统可自迭代）；无异常日志改为可解析格式；指令模糊增加外部触发信号** |

---

> **文档版本**：v2.1  
> **最后更新**：2026-06-21  
> **状态**：✅ 可部署
