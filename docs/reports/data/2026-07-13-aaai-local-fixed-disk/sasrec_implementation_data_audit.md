# E5 SASRec 实现与数据构建审计

## 结论

E5 在项目内部满足四域原子齐报、冻结 split/mapping、validation-only selector、tail-complete
full-catalog evaluator 和 seed 100 合同；它可以作为一个共同协议的外部序列模型锚点。它并非
原 SASRec 论文或常用官方仓库的逐项复现，而是面向 `paper_raw_v1` 的 SASRec-style audited
adapter。论文应使用“our common-contract SASRec adapter”或“an adapted SASRec baseline”，
不应写成“the official SASRec implementation reproduced under its native protocol”。

## 数据输入与样本构建

运行器不重新切分数据，而是读取每个数据集目录中的 `protocol.json`、`item_mapping.csv`、
`train_data.df`、`val_data.df` 和 `test_data.df`，并对这五个文件做联合 SHA-256。每行必须包含
`seq`、`len_seq` 和 `next`；训练、验证、测试行数必须等于 frozen protocol。目标 `next` 必须
位于 `[0,item_num-1]`，历史可以包含 catalog padding id `item_num`。

`paper_raw_v1` 历史是左 padding。adapter 在不改变 item ID、行或目标的情况下把有效后缀搬到
序列左侧，再用 `item_num` 右 padding。这一步是为了避免 PyTorch causal Transformer 在早期
位置出现全 mask 行。训练样本仍是 frozen frame 中的一行历史对应一个 next-item target；
adapter 没有从一条长序列内部重新生成 SASRec 常见的多位置自回归目标。

这一设计保证与 PreferGrow 的冻结样本单位一致，却会改变与其他论文 SASRec 数字的可比性。
其他工作可能采用每个序列多个位置、leave-one-out、不同最小交互过滤、不同最大长度或原生
negative sampling；仅比较数据集名称不足以判断实现优劣。

## 模型与优化

模型使用 `item_num+1` 的 item embedding、learned position embedding、PyTorch
`TransformerEncoder`、causal mask、padding mask，并在最后一个有效历史位置读取表示。输出层
是独立的 `Linear(hidden_size,item_num)`，没有与输入 item embedding 权重绑定。损失是对全部
真实 catalog items 的 full-softmax cross entropy，优化器为 AdamW，梯度范数裁剪为 1.0。

冻结配置为 hidden size 64、2 heads、2 layers、dropout 0.2、learning rate 0.001、weight
decay 0、batch size 512、evaluation batch size 1,024、最多 10 epochs、early-stop patience 2、
seed 100。常见 SASRec 实现可能使用 tied dot-product scoring、BCE/negative sampling、更多
epoch、不同 LayerNorm 布局或原论文超参数搜索。E5 因而验证的是该预声明 adapter，不是所有
SASRec 实现的性能上限。

## 评估与选择

每个 epoch 对 validation 全量排序，checkpoint 只按 row-weighted validation NDCG@10 选择；
选择后才对 test 运行一次同一 evaluator。候选集合是 `0..item_num-1` 的全部真实 catalog
items，padding 不进入输出层。adapter 没有过滤历史中已经交互过的 item；这一点只有在
PreferGrow 的共同 evaluator 同样不做 seen-item filtering 时才构成同尺比较。E5 的 artifact
明确记录 candidate policy、完整行数、selector/evaluator、split/config/mapping hash 和
开发期 test logging 披露。

## 四域结果

| 数据集 | best epoch | validation HR@10 | validation NDCG@10 | test HR@10 | test NDCG@10 |
|---|---:|---:|---:|---:|---:|
| Steam | 10 | 0.079013 | 0.043570 | 0.082194 | 0.046416 |
| ML1M | 10 | 0.249092 | 0.137651 | 0.224846 | 0.121677 |
| Beauty | 4 | 0.023256 | 0.011383 | 0.005811 | 0.002680 |
| ATG | 3 | 0.019062 | 0.010644 | 0.018023 | 0.009062 |

四个 test evaluated rows 分别为 80,651、85,405、2,237 和 1,942，均与 expected rows 相等。
E5 queue status 是 `passed_four_domain_atomic_group`，四个任务 return code 均为 0。未发现 JSON
或日志中的 non-finite 标记；这只能说明该运行没有记录 non-finite failure，不能排除数据分布
或训练配置导致的性能问题。

## Beauty 异常的边界

Beauty validation NDCG@10 为 0.011383，而 frozen best checkpoint 的 test NDCG@10 仅为
0.002680，下降约 0.008703；HR@10 从 0.023256 降至 0.005811。selector 没有使用 test，故该
现象不能解释为 checkpoint 直接按 test 选择。当前工件也不足以区分小样本 split shift、
10-epoch 训练预算、single-seed 波动、样本构建差异或模型适配问题。正文必须并列 validation
和 test，并把它称为 single-run validation-to-test decrease，不得只报 test 后宣称 SASRec 在
Beauty 上普遍失效。

## 为什么其他论文可能“差很多”或“好很多”

SASRec 的绝对数字对以下选择高度敏感：数据集版本与过滤阈值、leave-one-out 或预生成 frame、
每用户一个目标或多位置目标、最大序列长度、是否过滤 seen items、sampled negatives 或
full-catalog、输出层是否 tied、损失函数、训练 epoch、early stopping 和指标聚合。E5 与公开
数字只有在这些合同全部匹配时才可直接比较。当前最可核验的结论不是“其他论文错了”，而是
E5 是共同协议适配结果，其数值不等同于 native-protocol SASRec reproduction。

## 论文使用建议

E5 应承担“外部方法在同一数据/selector/evaluator 下的协议锚点”角色，而不是证明 PreferGrow
稳定优于经典序列模型。表注应同时给出 adapted implementation、seed 100、full-catalog、无
seen-item filtering、单目标 frozen rows、validation-only selector 和 test logging disclosure。
若篇幅不足，至少在主文 Setup 中声明 adapted common-contract，在补充材料给出完整审计。
