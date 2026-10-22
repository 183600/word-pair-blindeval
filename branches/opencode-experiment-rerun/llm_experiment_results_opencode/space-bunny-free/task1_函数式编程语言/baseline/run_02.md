# [rerun:space-bunny-free] 任务1 函数式编程语言 | 条件: baseline | 第 2 次

**Prompt:** 设计一个全新的函数式编程语言

**耗时:** 73.1s | **tokens:** 196/11485(推理 6842) | **finish:** stop

---

# Vela（星帆）——一门以"显式能力"为核心的函数式语言设计> **一句话定位**：Vela 是一门静态类型、不可变数据、**代数效应**（algebraic effects）的一等公民的函数式语言。它最独特的机制是**能力账本（Capability Ledger）**：*每一个副作用都必须在类型签名里露面，每一项能力都必须被显式授予。*

---

## 0. 设计目标与取舍

| 目标 | 决策 |
|---|---|
| 可审计性 | 效应集是类型的一部分，`grep` 一个函数就知道它碰过什么 |
| 无隐藏状态 | 无全局可变变量；状态必须经由 `State` 效应显式传递 |
| 无 null | `Maybe` 必须被匹配；穷尽性检查在编译期完成 |
| 零成本抽象 | handler 在 `-O2` 下被"效应融合"消除，退化为直接调用 |
| 务实 | 编译到 LLVM/WASM；能调 C；自举（self-host） |
| **不做什么** | 不做类、不做运算符重载的动态派发、不做隐式 monad 语法糖、不做 `unsafe` 逃逸口（安全代码中） |

---

## 1. 词法与整体形态

```vela
module sieve

ledger {IO, FS} // 本模块允许"处理"哪些效应（见 §6）

effect Get<S>
effect Put<S>
effect Yield<T>
effect Fail of String

type Shape =
  | Circle of radius : Float
  | Rect of width : Float * height : Float

fun area : Shape -> Float
  | Circle r -> pi * r * r
  | Rect (w, h) -> w * h
```

命名约定：小写下划线 = 函数/变量；大驼峰 = 构造器/模块；`'c'` = 字符；`0xFF` / `1_000_000` / `1.5e-3` = 数字；`_` = 通配。

注释：`//` 行注释，`/* */` 块注释，`////` 为**文档注释**（进 `vela doc`）。

**类型是可选的**：Vela 做完整的 HM + 行多态推断，标注只是给人和文档看的。

---

## 2. 类型系统

```
t ::= a // 类型变量（自动泛化）
    | t → t                          // 函数
    | {E₁,…,Eₙ} t                    // 效应化结果（"做这些事，得到 t"）
    | t * t                          // 元组
    | P<T,…> // 用户 ADT
    | {field : t, …}                 // 记录，字段名即唯一键
    | {field ?: t, …}                // 可选字段（宽度子类型）
    | ^t                             // 唯一类型（不可复制，见 §7）
    | forall a. t                    // 需显式标注时使用
```

要点：

- **行多态**：`fun zip_with f xs ys = ...` 自动获得 `∀a b. ({f : a→b} → [a] → [b] → [c])`。
- **效应行子类型**（深度子类型）：`{IO, Net} <: {IO}`。所以"能力窄化"免费。
- **无强制转换**：`1 as Float` 必须手写；数字字面量默认 `Int`，可标注 `1.0f`。
- **穷尽匹配**：漏一个构造器 → 编译错误，并给出"缺的分支 + 它在哪些行被构造"的提示。
- **字面量与守卫参与推断**：`| 0 -> …` 中的 `0` 是 `Int`；`| [] -> …` 精化为空列表。
- 保留字：`type effect fun val let rec where do handle perform case match ledger requires ensures unsafe module use open extern`.

---

## 3. 数据与模式匹配

```vela
type Option<T> = None | Some of T
type Tree<T>   = Leaf | Node of left : Tree<T> * value : T * right : Tree<T>

// 同一函数的多个子句 = 模式匹配（像 ML / Rust）
fun depth : Tree<T> -> Int
  | Leaf -> 0
  | Node (l, _, r) -> 1 + max (depth l) (depth r)

// 守卫、子模式、绑定、or模式、切片、范围
fun describe : Tree<T> -> String =
  match t with
  | Leaf -> "leaf"
  | Node (Leaf, v, Leaf) if v > 10 -> "solo big"
  | Node (Node _, _, _) | Node (Leaf, _, Node _) -> "tall"
  | Node (l, v, _) -> "{depth l} deep, root {show v}"

// 列表与字符串模式
fun shout : String -> String
  | "" -> "..."
  | s@(c :: rest) -> c.as_upper.to_string + shout rest
```

内建结构：`[T]`（`[]`、`x :: xs`、`x :: rest`）、`String`、`Bytes`、`Map<K,V>`、`Set<T>`、`Option<T>`、`Result<T,E>`、`Either<L,R>`、`Task<T>`、`Void`。

---

## 4. 核心表达式

```vela
let x = 1                          // 不可变
let f = \x -> x + 1                 // λ
if c then a else b                  // Bool，无真值化
a |> f |> g                        // 左管道
x |> add1 |> sub 1                // 也支持反管道<|
{ x = 1, y = 2 }                   // 记录；r.x 取字段，r?.x 返回 Maybe
r with { y = 9 }                   // 记录更新（结构共享）
e.other() // 方法糖：other(e)
[ x*x | x <- xs, x > 0 ]           // 推导式（绑定可以是效应化的！）
{ k : v | kv <- kvs }              // 记录推导式
"hi {name}, you are {age}"         // 内插
f $x // 显式应用
```

**控制流全部是表达式**，都有值：`if`/`match`/`do`/`handle`/`case` 都能出现在右侧。

局部互递归：

```vela
let rec go (a : Int, b : Int) = if b < n then go (b, a + b) else a
```

---

## 5. 模块与可见性

```vela
module std.state
  ledger {Get, Put}                // 只有列在这里的效应，本模块才能写 handle  effect Get<S>
  effect Put<S>
  alias State<S> = {Get<S>, Put<S>}

  fun run_state : (S -> {State<S>} a) -> S -> (a * S) =
    let store = ref_head S            // 内部唯一可变单元
    let r = f store.value
    handle
      | Get () -> f store.value
      | Put s (_ :: k) -> store := s; k ()
    (r, store.value)

  export run_state, Get, Put, State
  private store_of // 默认私有，export 才可见
```

`use std.state` 导入，`open std.list` 展开前缀。模块是**文件级**的，`vela add` 拉取第三方模块。

---

## 6. ★ 核心创新：能力账本

### 6.1 效应声明与 perform

```
effect E              // 无载荷
effect E of T         // 带一个载荷（perform E x : a）
alias Row = {E₁, …, Eₙ}
```

```vela
fun read_config : () -> {FS, Fail} (Map<String, String>) =
  match fs.read "config.toml" with
  | Ok s -> parse s // 可能 perform Fail
  | Err e -> perform Fail "no config: {e}"
```

### 6.2 三层强制

1. **调用点强制**：函数 `f` 的效应行 `ε_f` 必须被调用者 `g` 的行包含，否则报错。
2. **handler 强制**：只有出现在模块 `ledger` 里的效应，才能在该模块内被 `handle`。→ 库代码**不可能偷偷引入** I/O。
3. **传递性强制**：返回函数时效应不消失；闭包携带它实际用到的行。

```vela
error[E0431]: 效应 `Net` 不在 `summarise` 的能力集中
  ┌─ src/report.vela:12:10
  │
12│     let r = fetch url
  │            ^^^^^ 需要 {IO, Net}，但本函数签名只有 {IO}
  │
  = help: 显式提升签名 fun summarise : Url -> {IO, Net} Report
  = help: 或把网络结果作为参数传入（推荐）
```

### 6.3 能力窄化的实际价值

```vela
// audit.vela —— 唯一能碰网络的地方，一眼可查
fun refresh : () -> {IO, Net, Clock} Report =
  handle
    with std.net, std.clock
    | Net req k -> perform IO (fetch_low req) |> continue k
    | Clock ()  -> now()

// 分析层：签名里没有 Net，物理上无法发请求
fun render : Report -> {IO} String = …fun nightly : () -> {IO, Net, Clock} () =
  handle
    with std.net, std.clock        // 账本授予的顶层能力在此处消费
    | Net (GET u) k -> k (fetch u)
    | Clock () k -> k (Time.now)
    | IO () k -> log (k ())
```

### 6.4 审计工具

```console
$ vela audit --effects src/
src/report.vela
  render      : {IO} String                       pure-IO
  render_html : {IO} Html                          pure-IO
  refresh     : {IO, Net, Clock} Report            ⚠ Net 未被任何上层签名覆盖
unhandled in test: Net (2 处), Clock (1 处)
```

**这是 Vela 相对 Haskell（`unsafePerformIO` 式自由度）/ Rust（`unsafe` 逃逸口）的真正差异**：能力不是"你能偷偷做的事"，而是"类型里写着、账本里授权、审计工具能验证的事"。

---

## 7. 唯一类型（线性资源）

少数内建资源类型是 `^`（unique），只能移动一次：

```vela
fun with_file (p : Path) (f : ^File -> {IO, Fail} a) : {IO, Fail} a =
  h <- fs.open p Read
  let r <- f h                  // h 被移交给 f；f 不能把它留下  h.close()
  r
```

违反时报 `error[E0433]: '^File' 值被使用两次`，而不是运行时的 double-free。`Ref`、句柄、锁、内部 `store_of` 都用这个机制实现。

---

## 8. 契约（编译期/运行期可切换）

```vela
fun div (a : Int) (b : Int) : Int
  requires b /= 0
  ensures r * b == a
  = a / b

// 协议的接口级契约
interface Sized
  type T
  size : T -> Int
  requires size (x) >= 0
```

`vela build` 插桩检查；`-O release --assume-contracts` 消除。

---

## 9. 代数效应：三个完整例子

### 9.1 生成器

```vela
effect Yield<T>

fun fib : () -> {Yield} () =
  let rec go (a : Int, b : Int) =
    do
      yield a
      go (b, a + b)
  go (0, 1)

fun collect : (() -> {Yield<T>} a) -> [a] =
  handle
    | Yield x k -> x :: collect (k)

// 用起来像命令式，但效应老老实实写在这里
fun first10 : () -> {IO} [Int] =
  do
    xs <- collect (fib ())
    print (take 10 xs)
```

### 9.2 回溯解析（选择/失败是效应，不是 monad）

```vela
effect Choice
effect Fail of String

fun parse_word : () -> {Choice, Fail} String =
  do
    spaces ()
    cs <- take_while is_alpha
    if cs == "" then perform Choice else cs

fun parse_stmt : () -> {Choice, Fail} Stmt =
  do
    w <- parse_word ()
    perform Choice // 语义：请外层换个分支试试
    if w == "let" then … else Stmt.Expr (EVar w)

// 求所有解：Choice 被捕获 N 次
fun all : (() -> {Choice, Fail} a) -> [a] =
  handle
    | Choice k -> [x | k () -> x]        // 推导式里的绑定也可以带效应
    | Fail m  -> warn m; []

// 只求第一个解：Choice 被捕获一次就收敛
fun one : (() -> {Choice, Fail} a) -> Result<a, String> =
  handle
    | Choice _ -> Err "no more alternatives"
    | Fail m   -> Err m
```

对比 Haskell 需要 `Alternative`/`try` + monad transformer 栈，这里**异常控制流是类型化的、局部的、可组合的**。

### 9.3 并发：结构化 `Task`

```vela
effect Task

fun crawl (urls : [Url]) : {IO, Net, Task} [Page] =
  do
    // 并发度上限由 context 提供，作用域结束自动 join
    par_map (n = 8) (fetch_page) urls

// select：按最先完成者继续
fun race : {Task} a -> {Task} b -> {Task} (a | b) = …
```

`Task` 内建结构化作用域 +取消传播；编译器保证 `perform` 不会跨越未 join 的 scope（编译期错误，而非运行期泄漏）。

---

## 10. 外部接口

```vela
extern "c" fun strlen : (Ptr<u8>) -> Int
extern "c" struct Vec3 = { x : f64, y : f64, z : f64 }

unsafe do {FFI}
  fun read_raw (addr : Int) : Int = read addr // 必须写 safety 注释
```

安全代码里**没有**任意内存读；FFI/内联汇编全部收进 `unsafe` 块，且该块的效应必须显式列出 `{FFI, IO, …}`。

---

## 11. 标准库（首发）

```
core     Option Result List Map Set Str Bytes Mathstd.io   {IO} 流式读写、行缓冲、TextIO/ByteIO 分开
std.fs   {FS, IO} 路径、原子写入、mtime
std.net  {Net} HTTP/1.1+TLS、DNS（全部经 {Net} 效应）
std.env  {Env, IO} argv / 环境变量 / 时间 {Clock}
std.json {Fail} 解析器（用 Choice/Fail 效应写的）
std.test 契约断言、golden test、property test、{Clock, Random} 种子控制
```

`IO` 是一等效应而非特例：`std.io` 就是它的参考 handler，`vela run` 提供运行时实现。

---

## 12. 实现方案

```
源文件 → 词法/解析 → 表面 AST → 类型检查（HM + 行多态 + 穷尽性）
      → VIR（Typed IR，handler 显式化为帧记录）
      → 效应融合（识别"内联、一次性、不被重捕获"的 handler → 内联消除）
      → SSA / MLIR → LLVM · WASM · 原生 AOT
```

关键工程决策：

| 问题 | 方案 |
|---|---|
| 尾递归 | 分段值栈 + 循环回边，**语言级保证尾调用不增长栈**；深度非尾递归也可能撑爆栈 → 提供 `Stack` 显式栈 |
| `perform` 开销 | Koka 式**一次性分段续延**（复制栈段）；单次 perform ≈ 数纳秒。融合 pass 后多数 handler 归零 |
| 表示 | 64 位 NaN boxing；ADT = tag + 负载；小字符串内联 |
| GC |精确根 + **分代并发标记清除**（无停顿），每 task 一个 arena 可整体回收 |
| 泛型 | 字典化 + 少量单态化（热调用自动特化） |
| 编译器自举 | v1 用 OCaml 写（18 个月），v2 用 Vela 自己写（自举） |

---

## 13. 工具链

```console
$ vela new hello && cd hello
$ vela run            # 解释/JIT 执行，带热重载
$ vela check          # 只做类型检查 + 账本审计
$ vela test # 契约 +单元 +性质测试
$ vela build -O release --wasm
$ vela audit --effects --coverage # 能力账本 + 测试未覆盖的效应
$ vela doc --open
$ vela add std.http```

设计哲学：**错误信息即文档**。每个诊断都带代码片段、类型推导路径（可折叠）、一行可点击的 fix-it、以及相关标准库文档链接。

---

## 14. 与现有语言对比

| 维度 | Vela | Haskell | OCaml | Rust | Gleam/Koka |
|---|---|---|---|---|---|
| 效应显式性 | **签名 + 模块账本双强制** | 类型系统 | 较弱（需 mtl） | 无（`unsafe`） | 较显式 |
| `unsafe` 逃逸口 | 安全代码中不存在 | 无 | 无 | 有 | 无 |
| 穷尽匹配 | ✅ | ✅ | ✅（警告） | ✅ | ✅ |
| null | 无 | 无 | 有 | `Option` 但有 `null` | 无 |
| 资源管理 | `^` 线性 | 无 | 无 | 所有权 | 无 |
| 编译目标 | LLVM/WASM | GHC 多后端 | 多后端 | LLVM | BEAM/JS |
| 自举可行 | 计划中 | ✅ | ✅ | ✅ | ✅ |

一句话差异化：**Vela = Haskell 的效应纪律 + Rust 的能力审计 + 无 `unsafe` 的简洁前端。**

---

## 15. 语法速查

```
// 定义
type T = C1 of A * B | C2
effect E of P
fun f (x : A) (y : B) : R = e
fun f = | P1 -> e | P2 if g -> e
val p = e
requires/ensures  ledger export  private

// 使用
case e with | P -> e
match e with | P -> e | _ -> e
let rec f x = … |  let P = e |  do {stmts}
perform E v |  handle | E p k -> e
[a | b <- xs, cond]      [k : v | kv <- kvs]
r.field r?.field   r with {f = v}   {x = 1}
\x -> e   e |> f   e $x   "a{b}c"
```

---

## 16. 路线图与风险

| 阶段 | 目标 |
|---|---|
| v0.1（6 个月） | 解析器 + HM/行多态类型检查 + 基线解释器；效应、模式匹配、模块 |
| v0.3（18 个月） | VIR + LLVM 后端；效应融合；§ 标准库；热重载；`vela check` |
| v0.6（30 个月） | 自举：编译器用 Vela 重写，bootstrapping 通过 |
| v1.0 | 稳定 ABI + WASM 组件模型 + 并发 `Task` 成熟 |

**风险与对策**：
1. *handler 运行时开销* → 融合 pass + 静态"该 handler 是否可能被多次捕获"的可见性分析；必要时把 `perform` 降级为 setjmp/longjmp 方案。
2. *效应行类型错误信息难懂* → 专门的"能力差异"诊断（只显示集合差，而非完整推导树）。
3. *账本过于繁琐* → 账本可由编译器自动推断（"本模块处理过的效应全集"），只在 `ledger` 显式书写时用于**收紧**。
4. *学习曲线* → 教学子集 `vela --pedantic`：禁用所有隐式语法糖；`std.effect.tutorial`。

---

## 17. 收尾

Vela 的核心主张很简单：

> **副作用不是不能有，而是不能隐形。** 把"一个函数会做什么"写进它的类型、把"一个模块有权做什么"写进它的账本、把"一次资源移交"写进它的线性标注 —— 于是代码审查从"读逻辑"部分变成"核对集合"，审计从人工变成 `vela audit --effects` 一行命令。

如果你想，我可以接着展开其中任意一块：**完整的类型规则（Γ ⊢ e : τ ! ε）**、**VIR 与效应融合的算法细节**、**自举路线的前1000 行设计**，或者**手写一个 `vela` 解释器原型（Python，~600 行）**。
