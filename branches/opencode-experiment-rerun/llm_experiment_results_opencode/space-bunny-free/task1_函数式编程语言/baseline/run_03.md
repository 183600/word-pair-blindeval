# [rerun:space-bunny-free] 任务1 函数式编程语言 | 条件: baseline | 第 3 次

**Prompt:** 设计一个全新的函数式编程语言

**耗时:** 91.2s | **tokens:** 196/13913(推理 8622) | **finish:** stop

---

# 设计一门全新的函数式编程语言：**Sift（筛）**

> **定位**：一门**全函数（total）、无空值、模式优先、效果显式**的静态类型函数式语言。
> **信条**：*函数不是"输入→输出"，而是"把一个值筛成若干片段"。*

---

## 0. 设计出发点

现有 FP 语言大多在三个维度上做了妥协：

| 现状 | 问题 |
|---|---|
| `case`/`match` 是**控制流**（Haskell/OCaml/Rust/Elixir） | 模式无法复用、无法传递、无法组合；一旦不能"筛"，同一段解构逻辑要抄三遍 |
| `maybe`/`Option`/`nil`/`undefined`/异常 | 函数**可能是全函数也可能是偏函数**，调用方无法静态知道，`f x` 的类型签名在说谎 |
| 副作用藏在 monad/异常/可变状态里 | 效果是隐式的约定，不是类型的一部分；推理和优化都要靠约定俗成 |

Sift 的三个正交决策：

1. **模式是一等值**（`pattern a` 类型，有自己的 monad 代数），`case` 只是它的语法糖。
2. **每个函数都是全函数**：所有 ADT 穷尽检查在编译期完成；不存在 null / undefined / 运行时匹配失败。发散必须显式（`Delay`/`Diverges` 效果）。
3. **效果是类型的一部分**（行多态），处理器（handler）由**用户自己写**，不是库作者。

---

## 1. 一段最小但完整的程序

```sift
module Shapes where

import Data.List (foldl')
import Data.Double (showDouble)

data Point = Point { x :: Double, y :: Double }

data Shape
  = Circle  Point Double
  | Rect    Point Point  | Poly    (List Point)

-- 记录字段直接生成 pattern 值
origin :: pattern Point
origin = Point _ _          -- 构造器即模式

-- 面积：穷尽性 + 互斥性由编译器检查（少一条分支 = 编译错误，不是运行时报错）
area :: Shape -> Double
area s = case s of
  Point _ _ as p ->0.0                    -- 不会发生：编译器知道 Poly 分支不可达? 不会，见下
```

（上面 `Point` 不是 `Shape` 的构造器，故上一例不成立；正确写法见下。）

```sift
area :: Shape -> Double
area s = case s of
  Circle _ r -> pi * r * r
  Rect p q        -> let dx = abs (x q - x p); dy = abs (y q - y p) in dx * dy
  Poly ps         -> foldl' tri 0.0 (zipWith (\_ b -> b) ps (tail ps ++ [head ps]))
    where tri acc _ = acc   -- 真实实现见 §13

perimeter :: Shape -> Double
perimeter = \s -> case s of
  Circle _ r -> 2 * pi * r
  Rect p q   -> 2 * (abs (x q - x p) + abs (y q - y p))
  Poly ps    -> sum' (zipWith dist ps (tail ps ++ [head ps]))
 where dist a b = sqrt ((x a - x b) ^ (2 :: Int) + (y a - y b) ^ (2 :: Int))
```

注意：**没有 `throw`、没有 `_ -> ...` 这种"兜底垃圾分支"、没有 `undefined`**。

---

## 2. 核心创新一：模式代数（Pattern Algebra）

### 2.1 类型定义

```
data Match a = Matched a | NoMatch

pattern a ::= Any                                     -- 匹配任意值
            | Guard (a -> Bool) (pattern a)           -- 守卫 + 继续
            | Bind (a -> Match b) (pattern b)        -- 对内层值再筛
            | Alt    (pattern a) (pattern a)           -- 或```

运行：

```
(!)  :: pattern a -> a -> Match a        -- 中缀前缀：p ! v
p ! Any x = Matched x
p ! Guard g q x      = if g x then q ! x else NoMatch
p ! Bind f q x      = case f x of Matched y -> q ! y; NoMatch -> NoMatch
(Alt p q) ! x        = case p ! x of Matched y -> Matched y; NoMatch -> q ! x
```

`pattern` 因此是 **Monad**（`Bind` 就是 `>>=`，`Alt` 就是 `<|>`），并且有 `Functor`（`map`）、`Alternative`。

### 2.2 构造器即模式（关键的重载规则）

ADT 构造器**同时**是"解构函数"和"模式构造器"：

```sift
data List a = Nil | Cons a (List a)

-- 两种身份，同一个类型构造器
Cons        :: a -> List a -> Match (List a)      -- 解构(Cons p q)  :: pattern a -> pattern (List a) -> pattern (List a)   -- 组合
```

一条规则同时覆盖全部构造器，无需另设语法。

### 2.3 模式在绑定位置使用

```sift
headOr : List a -> a -> a
headOr xs d = (Cons Any Any<|> Any (const d)) ... -- 太啰嗦，所以给语法糖：
```

更好的方式：引入 `?`（or-default）与 `!`（应用）两个运算符：

```sift
firstTwo :: List (a, b) -> Maybe (a, b)
firstTwo xs = (Cons (Any, Any) ! xs)      -- 返回 Match，不抛错

-- 读起来像"解构赋值"
(a, b) <- firstTwo xs
```

而**多方程定义本身就是模式代数**：

```sift
len : List a -> Int
len Nil = 0
len (Cons _ t) = 1 + len t
```

编译器把每个方程编译成 `Alt` 分支。**"函数定义"与"模式值"是同一个东西的两种表面**——这是 Sift 语法上最独特的性质。

### 2.4 真实用途：模式即解析器

```sift
data Match a = Matched a | NoMatch
newtype Parser a = Parser (Pair (List Char) (List Char) -> Match (a, List Char))
```

`Parser` 就是 `pattern` 在"带剩余输入"上的实例化。于是：

```sift
digits :: Parser Char
digits  = Parser $ \s -> Matched (break isDigit s)

number :: Parser Double
number  = digits `many1` >>= \ds -> pure (readDouble ds)

expr :: Parser Double
expr    = chainl1 term (many (satisfy (`elem` "+-*/"))) term
```

同一个 `Matched/NoMatch` 代数服务两类需求：**结构化解构**与**语法解析**。库作者不再需要"parser combinator 宇宙"和"view pattern 宇宙"两套互不兼容的东西。

---

## 3. 核心创新二：全性（Totality）与"显式不安全"

**规则**

1. 严格求值（call-by-value）。ADT 构造器、记录、闭包都是数据。
2. `case` 的分支集合在**编译期**被证明：穷尽（exhaustive）且互斥（disjoint）。否则报**编译错误**，不是 `MatchError`。
3. 函数是全函数：给定类型内的输入，函数必定返回值。
4. 唯一的不全性是显式的：

```sift
effect Diverges = { spin : Unit -> Unit }

delay :: (a => b) -> Delay a          -- 不透明；一个受控的"洞"
force :: Delay a => a                 -- 效果：可能不终止（Diverges）
unsafe :: ... -- 逃逸舱，必须显式标注且被 linter 追踪
```

5. **终止性检查**：对多方程函数做结构递归检查——递归调用必须作用在某个方程"刚解构出来的子项"上（Coq/Agda 的 guard condition 思路，但落在**模式**上，因此天然与 Sift 的语法一致）。这让"写不出非终止函数"成为**类型检查的一部分**。

**代价**：不能随手写 `f x = f x` 式的无限循环；必须写 `f = unsafeFixpoint g`。我们认为这个代价换来的静态保证是值得的，并且 §15 给了逃生通道。

---

## 4. 核心创新三：效果行与用户可定义处理器

### 4.1 两个箭头

```
->   纯函数
=>   可能带效果的计算；效果集写在类型里（行多态）
```

```sift
effect Ledger s = {
  balance : Account -> Double => Double,
  commit  : Tx -> Unit => Unit,
  tell    : Msg -> Void => Void
}

data Void                              -- 空类型（无构造器）
```

`Void` 使"抛错"变成普通函数：`tell m : Void => Void` 永不返回，控制流自然汇合。

### 4.2 处理器由用户写

```sift
runLedger :: (forall s. Ledger s => a) -> s -> a
runLedger c s0 = handle c with Ledger s0 by
  balance = \acc s k -> k (lookup acc s) s
  commit  = \tx   s k -> k unit (insert tx s)
  tell    = \m    s _ -> unreach m -- 一次性处理器：不可 resume
```

**语义**：处理器的每个子句类型是 `o → Resume a b → a => b`，其中 `Resume a b = b => a`。默认处理器是**一次性（one-shot）**的，且编译器对处理器体施加**自然性检查**：

> `k` 至多被调用一次，且不能逃逸到处理器体之外。

这保证了"处理器无法观察挂起次数"，从而给出干净的等式理论（`c |> handle h = handle (c |> handle h')`，可自由变换律）。Koka/OCaml 的多用途处理器没有这个保证，会产生"深 handler污染后续代码"的著名问题；Sift 用**限制换取可推理性**。

### 4.3 标准效果是语法糖

`State`、`Reader`、`Writer`、`Except`、`Choice`、`Async` 全部是 `Prelude` 里用同一套 `handle` 写的库函数，不是编译器内建。

---

## 5. 类型系统

| 特性 | 决定 |
|---|---|
| 多态 | **Hindley–Milner + let-泛化**，rank-1。刻意不支持 rank-N：换推理与报错体验 |
| 值限制 | **没有**（无副作用 ⇒ 泛化安全） |
| 记录/效果 | **行多态 + 主类型求解**（Koka 风格：行变量抽取，保留 principal type） |
| 线性/仿射 | 可选多重性：`File`（`1`）、`Buffer`（`0..1`，可拷贝或丢弃）、`Span`（`0..n`）。默认全是无限制的"金"类型 |
| 相等类型 / GADT | v1 不支持（保持 HM 简单），列入路线图 |
| 依赖类型 | v1 不支持；路线图是"类型即值 + 反射式证明" |
| 空 | 无 `null`、无 `undefined`；`Maybe`/`Either` 是显式的 |

```sift
process :: File -> (Bytes -> Result E Bytes) => Bytes
open  :: Path -> File => File        -- File 是线性的：必须恰好用一次
close :: File -> Unit => ()
```

---

## 6. 语义（核心规则）

```
(λx.e) v            ⟶ e[x := v]              --严格 CBV
Cons a l ⟶ alloc(Cons, a, l)
Guard g p ! v       ⟶ if g v then p ! v else NoMatch
Alt p q ! v         ⟶ p ! v  (结果为 NoMatch 时) q ! v
case v of p₁→e₁…pₙ→eₙ  ⟶ (p₁<|> … <|> pₙ) ! v  ⋈ bind
c |> handle h       ⟶ 将 h 的子句替换 c 中的 op 调用
```

**编译期求值**：`pattern` 值与模块级常量都是普通的**全函数值**，因此常量折叠器可以把它**归约成决策树**（Maranget 的模式矩阵编译）。→ `p ! v` 在 `p` 静态已知时**零成本**；只有在 `p` 运行时才知道时，才走一个极小的 `Match` 字节码 VM。这与"动态模式在 ML 语言里很慢"的批评正面回应。

---

## 7. 编译器与运行时

**前端**：手写递归下降 + layout 敏感词法分析；类型检查器用 HM约束求解 + 行约束求解，支持增量检查与**类型导向的错误恢复**（一个错误不会级联出 50 条）。

**中端**：
1. 模式矩阵 → 决策树（覆盖 pattern algebra）
2. 闭包转换 + let-floating + 全函数化（boxed消除）
3. 线性类型的资源路径插入隐式释放检查**ADT 表示**：封闭且已知的构造器集合 → **扁平化布局**（标签 + 非空字段数组，`Cons` 只多一个指针）。构造器集开放的类型 → 链式。

**后端**：LLVM（原生）+ Wasm（组件化）。

**GC**：分代、非移动、并发标记-清除（无 STW 暂停），保证**确定性**（便于做 wasm/形式化验证）。移动 GC 被排除，因为线性类型 + 移动需要额外 rewrite阶段。

**性能目标**（设计目标，非实测）：原生后端在 `fib`/矩阵/树遍历等热循环上与 ML 系语言同量级；Wasm 后端与手写 Wasm 的差距在一个数量级内。

---

## 8. 标准库 `Prelude`（刻意很小）

| 模块 | 内容 |
|---|---|
| `Match` | `pattern` 代数（**在核心里**，不在库里） |
| `Data.{List,Maybe,Either,Pair,NonEmpty}` | 容器 |
| `Effect.{State,Reader,Writer,Except,Choice,Async}` | 用 `handle` 写的 |
| `Parse` | 复用 `Matched/NoMatch` 的解析器 |
| `Data.{Map,Set,Text,Vector}` | 平衡树 / rope |
| `Prelude` 内部用 `unsafe` 的地方被限制在单个模块，并由 `sift check --strict` 审计 |

---

## 9. 工具链

```
skein new bank # 脚手架
sift check             # 类型检查（毫秒级增量）
sift build             # 编译（--emit=llvm|wasm）
sift test              # 黄金测试 + 性质测试（QuickCheck 风格，纯库实现）
sift fmt               # 规范化排版（layout 语言需要强规范）
sift doc               # 所有代码块都被类型检查并执行（文档即测试）
sift lsp               # 编辑器：内联类型、补全、重构```

**包管理器 `skein`（织）**：语义化版本 + 逐包构建哈希 + 内容寻址缓存 + 签名。默认沙箱只有文件/网络/时钟三个 capability，FFI 需要显式申请并写入 `sift.toml`。

---

## 10. 与现有语言对比

| | Sift | Haskell | OCaml | Rust | Idris/Agda | Koka/Effekt |
|---|---|---|---|---|---|---|
| 模式是一等值 | ✅ 完整代数 | ⚠️ view patterns | ⚠️ first-class variants | ❌ | ❌ | ❌ |
| 全函数保证 | ✅ 强制 | ❌ | ❌ | ⚠️ `unsafe` | ✅ | ❌ |
| 无 null/undefined | ✅ | ✅ | ❌ | ⚠️ `Option` 未强制 | ✅ | ✅ |
| 效果可推断、用户可定义处理器 | ✅ | ❌（monad 类） | ❌ | ❌ | ❌ | ✅ |
| 处理器语义干净（自然性） | ✅ 一次性+检查 | — | — | — | — | ❌ 多用途 |
| 依赖类型 | ❌ (v1) | ❌ | ❌ | ❌ | ✅ | ❌ |
| 所有权/借用 | 仅线性处 | ❌ | ❌ | ✅ 全程 | ❌ | ❌ |
| 运行时可替换 | ✅ | ❌ (GHC) | ❌ | ❌ | ❌ | ✅ |

**诚实的自我定位**：Sift 站在"ML 的可预测性 + Haskell 的抽象 + Idris 的严谨性 + 现代效果系统的表达力"的交叉点，**主动放弃** rank-N 类型和依赖类型（v1），用它们换取一个**十行能读懂的类型签名**和**零 surprised 的语义**。

---

## 11. 完整示例：带效果的银行转账

```sift
module Bank where

import Data.List (foldl')
import Data.Int (show)
import Data.Double (showDouble)

type Account = Int

data Tx  = Deposit Account Double | Withdraw Account Double
data Msg = Insufficient Account Double | NegativeAmount

effect Ledger = {
  balance : Account -> Double => Double,
  commit  : Tx -> Unit => Unit,
  tell    : Msg -> Void => Void
}

report :: Msg -> String
report m = case m of
  Insufficient acc gap -> "account #" ++ show acc ++ " short by " ++ showDouble gap
  NegativeAmount        -> "amount must be positive"

-- 效果行写在类型里；tell 让 Void 分支自然汇合
transfer :: Account -> Account -> Double => Unit
transfer from to amt
  | amt <= 0    = tell NegativeAmount
  | otherwise   =
      let bal = balance from in
      if bal < amt then tell (Insufficient from (amt - bal))
      else do { commit (Withdraw from amt); commit (Deposit to amt) }

-- 处理器：一次性 tell = 提前退出 → Either
settle :: Account -> Account -> Double => Either Msg Unit
settle f t a = handle (transfer f t a) with Ledger by
  balance = \_ s k -> k 0.0 s
  commit  = \_ s k -> k unit s
  tell    = \m s _ -> Left (m, s)

-- 状态处理器：state 进类型，不进运行时
runLedger :: (State (Map Account Double) => a) -> Map Account Double -> a
runLedger c s0 = handle c with State s0 by
  get = \u s k -> k s s
  put = \s' u k -> k unit s'

finalBalance :: List Tx -> Either Msg Double
finalBalance txs = settle0 0 0.0 <|> pure () -- 具体化见下apply :: List Tx -> State (Map Account Double) => ()
apply txs = foldl' step unit txs where
  step : Unit -> Tx -> State (Map Account Double) => Unit
  step _ tx = case tx of
    Deposit  a x -> put (insert a x (get unit))
    Withdraw a x -> put (insert a (-x) (get unit))

demo : List Tx -> String
demo txs = case runLedger (apply txs) empty of
  m | null m -> "no accounts"
 | otherwise -> "balance = " ++ showDouble (lookup 0 m)
```

值得注意：**没有一个 `try/catch`，没有一个 `null` 检查，没有一个"未定义"分支**。所有可能的失败都表现为 `Either Msg Unit` 这样的**数据**。

---

## 12. 非目标（明确不做）

- ❌ 编译期 OOP / 类继承 / 运算符重载（多态靠函数与记录）
- ❌ 宏的过程式卫生卫生（v1）→ 计划：把宏当作**在编译期求值的纯函数**（这是全函数性的红利）
- ❌ 隐式转换、隐式数值塔- ❌ 面向对象 / 数组式可变循环（可变数组走 `Buffer` +线性所有权）

---

## 13. 已知风险与对策

| 风险 | 严重度 | 对策 |
|---|---|---|
| 全性检查误伤合法程序（高阶递归、`foldl`） | 高 | 只允许**结构递归**；提供 `Fix` 组合子作为受控逃逸，并单独标记 |
| 一次性处理器的自然性检查过严，阻碍写 `get`/`put` 之外的 handler | 中 | 提供 `Resume` 的受限提升 `lift0/lift1`（仍受自然性约束） |
| 行的主类型求解实现复杂度 | 中 | 借鉴 Koka 的"行变量抽取 + principality 测试"；v1 只支持**无歧义**子类型 |
| 线性类型的可用性（要频繁 `close f` 很烦） | 中 | 区域（region）推断 `using f do {...}`，只在需要处线性化 |
| 生态为零 | 高 | 目标用户是**教学 / 形式化 / 嵌入式 + 工具链**；先做正确的核心，不做社区 |

---

## 14. 路线图

```
v0.1  核心：ADT + 模式代数 + HM + layout + LLVM
v0.2  行多态 + 效果 + handle + Prelude(Effect, Parse)
v0.3  Wasm 后端 + skein + LSP + sifmt
v0.4  线性类型 + 区域推断 + C FFI
v0.5  编译期求值 / 反射（宏、代码生成、证明检查）
v1.0  稳定语法 + 自举（用 Sift 写 Sift 的后端）
```

---

## 15. 一页纸规范摘要

```
程序 = 模块*
模块     = "module" 标识 ("where")? 声明*
声明     = 导入 | 数据 | 效应 | 类型别名 | 定义 | 签名
数据     = "data" 标识 类型参数* "=" (构造器 |)+ 派生*
构造器   = 标识 字段* |标识 "{" (字段 ",")* "}"
效应     = "effect" 标识 类型参数* "=" "{" (op ",")* "}"
op       = 标识 ":" 参数* ("=>")? 返回类型
定义     = 函数 | 值
函数     = (标识 | 中缀运算) 参数+ "=" 表达式
表达式   = 字面量 | 变量 | λ | 应用 | do | case | handle | 中缀运算
应用 = 原子+
原子     = 字面量 | 标识 | "(" 表达式+ ")" | 构造器 | 块 | 列表 | 记录
case     = "case" 表达式 "of" (模式 "->" 表达式)+
模式     = 构造器 模式* | 标识 | 字面量 | (模式, 模式+) | 标识 "{" 字段模式 "}"
绑定     = 模式 ("<-" 表达式)?
守卫     = ("|" 表达式 "=" 表达式)+
注释     = "--" 行 | "{-" 嵌套块 "-}"
布局     = 布局规则（与 Haskell 一致，块内缩进 > 外层）
```

---

## 16. 总结

Sift 的全部设计可以压缩成三句话：

1. **模式是值**——`pattern a` 构成 monad 代数，解构、解析、函数定义是同一件事的三种表面；
2. **函数都是全函数**——穷尽性是编译期义务，不全性必须显式付费；
3. **效果是类型里的行**——用户写处理器，一次性+自然性检查换来可推理的语义。

它的代价是放弃 rank-N 类型、依赖类型、成熟生态；它的回报是：**任何一个 Sift 程序的类型签名都告诉你它会不会崩、会不会终止、会做什么副作用**——而这正是今天大多数"函数式"程序所缺的那一点确定性。
