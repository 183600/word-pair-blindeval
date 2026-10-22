# [v2:deepseek-v4-pro 评 deepseek-flash] task6 ML架构 | run 3 | swap=True

**Winner:** baseline (raw=B)

**A:** cleaned_word_pairs | **B:** baseline

---

## 回答 A

### 一种稀疏模块化机器学习架构：TMC-Net

**全称：Tide–Mortise–Coral Network，TMC-Net。**

核心思想：模型由可动态生长和重组的模块组成；计算不是固定层堆叠，而是由可生长的珊瑚模块组成，通过榫卯路由按结构兼容性拼接；全局由风筝控制器约束表示轨迹，并用琥珀记忆和灯塔对齐器维持长期记忆与安全方向。

#### 1. 潮汐双时间尺度输入层
输入序列同时进入两个状态流：

- **快潮汐流**：短时间尺度状态，处理局部语法、即时上下文；
- **慢潮汐流**：长时间尺度状态，处理主题、用户意图、长期依赖。

两流通过门控小波式更新：

\[
h_t^{f} = \text{FastTide}(h_{t-1}^{f}, x_t)
\]
\[
h_t^{s} = \text{SlowTide}(h_{t-1}^{s}, h_t^{f})
\]
\[
z_t = \text{Gate}(h_t^{f}, h_t^{s})
\]

快流处理短时局部变化，慢流处理长时全局变化；模型可按输入动态决定记忆深度与遗忘程度。

#### 2. 珊瑚生长模块
基础计算单元称为 **Coral Polyp**，是一个小型的稀疏计算块。每个 Coral Polyp 有：

- 局部参数；
- 特征签名向量；
- 使用统计；
- 与其他模块的兼容矩阵。

训练中，若某类模式反复产生高重构误差，则“发芽”新模块；长期低贡献模块则“白化”并剪除。这样网络不是固定深度，而是逐步生长、萎缩和重组。

#### 3. 榫卯路由
传统 MoE 常用 Top-k 路由。TMC-Net 使用 **Mortise–Tenon Routing**：

对当前 token/状态计算查询 \(q\)，并计算其与各模块签名 \(s_i\) 的结构兼容度：

\[
c_i = q^\top W s_i - \lambda \cdot \text{shape\_mismatch}(q,s_i)
\]

优先选择“形状适配”的模块，而不是单纯激活值最大的模块。被选模块不是并列相加，而是按兼容关系形成一条短计算链，模块之间通过结构兼容性相互约束：

\[
\text{Path} = \text{BeamSearchCompose}(c_1,\dots,c_n)
\]

这样可减少冗余专家组合，提高可解释性。

#### 4. 风筝控制器
全局控制器输出一个“线向量” \(l_t\)，约束隐状态不要飞得太远：

\[
\tilde{h}_t = h_t + \alpha l_t
\]

同时加入信任域损失：

\[
L_{\text{kite}} = \| h_t - \Pi_{\text{trust}}(h_t, l_t) \|^2
\]

该控制器允许探索，同时保持表示轨迹稳定，防止长程推理漂移。

#### 5. 琥珀记忆
模型维护不可变或半不可变的片段记忆：

- 高价值状态写入“琥珀检查点”；
- 检索时按内容相似度、时间、来源可信度联合匹配；
- 旧记忆通过“潮汐衰减”逐步压缩，而不是简单覆盖。

记忆更新：

\[
m_k = \text{AmberWrite}(h_t) \quad \text{if utility}>\tau
\]
\[
\text{Retrieve}(q) = \text{TopK}_{k}(\text{sim}(q,m_k) \cdot \text{recency}_k \cdot \text{trust}_k)
\]

#### 6. 灯塔对齐器
外部或冻结的评估器作为“灯塔”，在路由、记忆检索和输出阶段提供安全与目标对齐信号。若某条榫卯路径偏离灯塔方向，则降低其兼容分或触发回退路径。

\[
L_{\text{beacon}} = \max(0, \text{margin} - \text{align}(y,\text{Beacon}(x)))
\]

#### 7. 蜂群编译器
训练稳定后，高频路由路径会被编译成融合内核。这样推理时不必每次完整搜索，兼顾动态结构与低延迟。

#### 训练目标
总损失可写为：

\[
L = L_{\text{task}} +
\alpha L_{\text{coral-sparse}} +
\beta L_{\text{route-balance}} +
\gamma L_{\text{mortise-fit}} +
\delta L_{\text{kite}} +
\epsilon L_{\text{amber}} +
\zeta L_{\text{beacon}}
\]

其中：

- \(L_{\text{coral-sparse}}\)：鼓励稀疏生长；
- \(L_{\text{route-balance}}\)：防止路由塌缩；
- \(L_{\text{mortise-fit}}\)：鼓励结构兼容组合；
- \(L_{\text{kite}}\)：约束表示轨迹；
- \(L_{\text{amber}}\)：对比式记忆读写；
- \(L_{\text{beacon}}\)：安全与目标对齐。

#### 推理流程
1. 输入进入快/慢潮汐状态；
2. 计算 token 与珊瑚模块的榫卯兼容度；
3. 用束搜索拼接一条短计算路径；
4. 风筝控制器调节路径深度与探索范围；
5. 检索琥珀记忆；
6. 灯塔对齐器进行安全审查或路径重定向；
7. 蜂群编译器将高频路径融合输出。

#### 与现有架构的区别
- 对比 Transformer：不是固定层堆叠，而是动态生长模块图；
- 对比 MoE：不是简单 Top-k 专家加权，而是结构兼容的榫卯式路径拼接；
- 对比 RNN/SSM：引入快慢双潮汐状态与周期记忆；
- 对比普通记忆网络：加入不可变琥珀检查点、潮汐衰减和可信检索；
- 对比普通对齐：把外部灯塔信号嵌入路由与记忆，而不仅放在最终输出。

**一句话概括：TMC-Net 是一个可动态生长、按结构兼容性组合、具备长期记忆与安全对齐约束的稀疏模块化机器学习架构。**

---

## 回答 B

下面提出一个概念上较完整、可落地实验的机器学习架构草案。它不是已验证的 SOTA，而是一个可用于研究的新架构方案。

---

## 架构名称：DyRAME  
**Dynamic Routing with Associative Memory and Elastic computation**  
中文：**动态路由—联想记忆—弹性计算网络**

### 1. 核心思想
传统网络通常采用固定计算路径。DyRAME 让每个样本或 token 根据上下文、不确定性和计算预算，动态决定：

1. 使用哪些专家模块；
2. 是否读取长期/情景记忆；
3. 需要递归计算多少步；
4. 是否写入新记忆；
5. 是否需要弃权或请求更多信息。

它把 **稀疏专家路由 MoE、可读写联想记忆、自适应计算、不确定性门控** 统一到一个循环式主干中。

---

## 2. 总体结构

```text
输入 x
  ↓
多模态编码器 / Tokenizer
  ↓
上下文路由器 Context Router
  ↓
┌──────────────────────────────────────┐
│        弹性循环核心 Elastic Core       │
│                                      │
│  h_t ──> Router ──> 专家池 E_k         │
│    │        │                         │
│    │        └──> 记忆读取 Memory Read  │
│    │                  │               │
│    └──> 共享更新块 F(h_t, e_t, m_t)    │
│                  │                    │
│           Halting / 不确定性门控        │
└──────────────────────────────────────┘
  ↓
记忆写入门控 Memory Write
  ↓
输出解码器 / 任务头
```

---

## 3. 关键模块

### 3.1 多模态编码器
将文本、图像、音频或表格输入编码为 token 序列：

\[
H^0 = \text{Encoder}(x), \quad H^0=\{h_1^0,\dots,h_n^0\}
\]

并为每个 token 加入模态标签、位置编码和任务上下文。

---

### 3.2 上下文路由器
路由器根据当前 token、全局上下文和计算预算，输出：

- Top-K 专家选择；
- 记忆查询向量；
- 是否继续递归计算；
- 不确定性估计。

\[
r_i^t = \text{Router}([h_i^t; c; b])
\]

其中 \(c\) 是全局上下文表示，\(b\) 是计算预算向量。

专家路由权重：

\[
\pi_i^t = \text{TopKSoftmax}\left(\frac{W_r r_i^t}{\tau}\right)
\]

只激活少量专家，降低计算量。

---

### 3.3 联想记忆模块
设置两类记忆：

1. **快速情景记忆**：存储近期样本、上下文和中间推理结果；
2. **慢速语义记忆**：通过 EMA 或原型聚类压缩长期知识。

记忆读取采用多头注意力：

\[
m_i^t = \text{Attention}(W_q h_i^t,\; M_K,\; M_V)
\]

记忆写入由“惊讶度 + 新颖度 + 不确定性”共同控制：

\[
p_{\text{write}} = \sigma(a \cdot \text{Surprise} - b \cdot \text{Novelty} + c \cdot \text{Uncertainty})
\]

只有预测误差高、且与已有记忆差异较大的样本才写入，避免记忆爆炸。

---

### 3.4 稀疏专家池
专家池包含：

- 通用专家：所有任务共享；
- 模态专家：文本、图像、音频等；
- 任务专家：特定任务或领域；
- 记忆增强专家：专门处理检索到的信息。

专家输出：

\[
e_i^t = \sum_{k \in \text{TopK}} \pi_{ik}^t E_k([h_i^t; m_i^t])
\]

---

### 3.5 弹性循环计算
共享更新块可重复调用，但每个 token 的计算深度不同：

\[
h_i^{t+1}
= \text{LayerNorm}\left(h_i^t + g_i^t \cdot F([h_i^t; e_i^t; m_i^t])\right)
\]

其中 \(g_i^t\) 是门控系数。

停止概率：

\[
\lambda_i^t = \sigma(W_h [h_i^t; \text{Entropy}(\pi_i^t); d_{\text{mem}}])
\]

累计停止概率超过阈值或达到最大步数时停止：

\[
\sum_{t=1}^{T_i} \lambda_i^t \ge 1-\epsilon
\]

这样简单 token 少算，复杂 token 多算。

---

### 3.6 不确定性门控
不确定性由三部分组成：

\[
u_i = \alpha \cdot H(\pi_i) + \beta \cdot \text{Disagreement} + \gamma \cdot d_{\text{mem}}
\]

其中：

- \(H(\pi_i)\)：路由熵；
- Disagreement：多个专家或 dropout 预测的不一致；
- \(d_{\text{mem}}\)：与记忆键的最近距离。

当不确定性过高时，网络可以：

- 增加递归步数；
- 强制读取记忆；
- 调用更多专家；
- 输出弃权或请求人工标注。

---

## 4. 训练目标

总损失可写为：

\[
\mathcal{L}
= \mathcal{L}_{\text{task}}
+ \lambda_1 \mathcal{L}_{\text{budget}}
+ \lambda_2 \mathcal{L}_{\text{balance}}
+ \lambda_3 \mathcal{L}_{\text{retrieval}}
+ \lambda_4 \mathcal{L}_{\text{calibration}}
+ \lambda_5 \mathcal{L}_{\text{sparse}}
\]

各项含义：

- \(\mathcal{L}_{\text{task}}\)：主任务损失；
- \(\mathcal{L}_{\text{budget}}\)：平均计算步数或 FLOPs 惩罚；
- \(\mathcal{L}_{\text{balance}}\)：专家负载均衡；
- \(\mathcal{L}_{\text{retrieval}}\)：记忆读取的对比学习损失；
- \(\mathcal{L}_{\text{calibration}}\)：不确定性校准损失；
- \(\mathcal{L}_{\text{sparse}}\)：路由和写入门的稀疏正则。

训练可分三阶段：

1. **预训练阶段**：软路由 + 负载均衡；
2. **记忆预热阶段**：读写记忆、对比检索、回放缓冲；
3. **联合微调阶段**：加入计算预算、校准和弃权机制。

---

## 5. 关键创新点

1. **路由、记忆、计算深度三者联合决策**：不是单独做 MoE 或自适应计算，而是让一个统一路由器同时决定。
2. **惊讶度驱动的记忆写入**：只写高信息量样本，降低记忆污染和存储成本。
3. **不确定性感知的弹性计算**：高不确定性样本获得更多专家和更多递归步。
4. **可解释性强**：可以追踪每个样本使用了哪些专家、读取了哪些记忆、计算了多少步。
5. **适合持续学习**：情景记忆支持新知识快速写入，语义记忆支持长期巩固。

---

## 6. 适用场景

- 长上下文问答与文档推理；
- 多任务多模态学习；
- 持续学习与在线适应；
- 边缘设备上的条件计算；
- 高风险场景中的不确定性校准和弃权预测。

---

## 7. 可能的局限

- 路由器可能坍缩到少数专家，需要较强的负载均衡；
- 记忆读写会带来隐私和安全问题；
- 训练和推理系统复杂度高于标准 Transformer；
- 记忆写入策略若设计不好，可能引入噪声；
- 自适应循环会增加延迟控制难度。

---

## 8. 最小可行实验版本

可以先实现一个简化版：

```text
Transformer 编码器
+ Top-2 MoE 层
+ 一个可微分键值记忆库
+ 每个 token 最多 4 步共享循环块
+ 基于路由熵的简单 halting
```

基线对比：

- 标准 Transformer；
- MoE Transformer；
- Universal Transformer；
- RETRO / 检索增强模型；
- Perceiver / 长上下文模型。

评估指标：

- 任务准确率；
- 平均 FLOPs / token；
- 专家利用率；
- 记忆命中率；
- ECE 校准误差；
- 持续学习遗忘率；
- 长尾和低资源任务表现。

---

这个架构的核心卖点是：**让模型在“调用哪个专家、是否查记忆、算多深、是否写记忆”四个维度上做统一的动态决策。** 如果要做论文，可以重点验证“记忆写入门控 + 路由熵驱动计算深度”是否比单独 MoE 或单独检索增强更有效。

---

## 评审输出

{"A": {"logic": 8, "concreteness": 9, "actionability": 7, "originality": 10, "overall": 8}, "B": {"logic": 9, "concreteness": 9, "actionability": 9, "originality": 8, "overall": 9}, "winner": "B", "reason": "B 的结构更统一、可解释和可落地，给出了最小可行实验、基线和局限；A 原创概念丰富但工程落地与自洽性略弱。"}
