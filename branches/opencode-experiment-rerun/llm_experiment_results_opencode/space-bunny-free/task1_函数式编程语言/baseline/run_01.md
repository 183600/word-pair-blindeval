# [rerun:space-bunny-free] 任务1 函数式编程语言 | 条件: baseline | 第 1 次

**Prompt:** 设计一个全新的函数式编程语言

**耗时:** 33.6s | **tokens:** 196/5439(推理 1277) | **finish:** stop

---

# Vela 语言设计文档 v0.1

> 目标用户：既要"函数式的干净语义"，又不愿放弃现代工程的可用性与性能的程序员。
> 一句话定位：**一门以显式效应、线性资源与全函数式语义为核心的通用编译型函数式语言。**

---

## 一、哲学与五条设计原则

| 原则 | 含义 |
|---|---|
| **P1 默认纯净，效应显式** | 纯函数的类型签名里不出现任何"看不见的副作用"。副作用（IO/异常/状态/并发）必须出现在类型中，可被组合、可被审查。 |
| **P2 数据不可变，资源有类型** | 所有绑定与数据结构不可变；不可复制/不可丢弃的资源（文件、锁、socket）用线性类型在类型层面强制唯一所有权。 |
| **P3 无隐藏失败** | 没有 `null`，没有未初始化变量，没有隐式整数溢出。所有函数要么全定义、要么签名里含 `Partial`。 |
| **P4 静态可推理，动态可落地** | 一切语义决策（类型、效应、资源流）在编译期确定；运行时无 RTTI、无隐式转换、无可变全局。 |
| **P5 零成本抽象** | 高阶抽象（迭代器、解析器、effect）通过内联+融合编译，不产生堆分配；尾部调用与递归被保证优化。 |

命名理由：Vela 是南船座的帆——小而稳，承载长途。

---

## 二、语言核心特性一览

- **代数数据类型 + 模式匹配**（穷尽性检查、绑定、守卫、区间、or/as 模式）
- **Hindley–Milner 类型推断 + 行多态**（记录类型与效应类型都是开放行）
- **效应系统（Effect Rows）**：多效应标注、自动效应插入、`?` 传播运算符、effect handler（代数效应）
- **线性类型 /唯一类型（Unique Types）**：`fn(File) -> a` 式的借用、`defer` 自动释放、编译期资源泄漏诊断
- **GADT + 类型驱动分派 + 约束集**（`Num`、`Ord`、`Functor`，静态解析、无字典歧义）
- **全函数性（totality）检查**：非终止递归在未标注 `partial` 时报错
- **结构化并发**：`task` / `chan` / `select`，无裸线程、无共享可变状态
- **能力式模块系统**：导入即授予权限，跨包边界强制
- **一等函数 + 协程 + 宏**（卫生宏，编译期展开）
- **编译到 SSA/LLVM**，也有紧凑字节码 VM（用于脚本与教学）

---

## 三、语法

Vela 采用**花括号块 + 可省略分号**，风格介于 Rust / Swift / Scala 3，避免 Python 式布局歧义，同时支持可选的 `indent` 块形式。

### 3.1 Hello World

```vela
fn main() -> unit ! io {
  io.println("Hello, Vela!")
}
```

### 3.2 代数数据类型与模式匹配

```vela
type Shape =
  | Circle(radius: f64)
  | Rect(w: f64, h: f64)

fn area(s: Shape) -> f64 =
  match s {
    Circle(r) => std.pi * r * r
    Rect(w, h)        => w * h
  }

fn describe(s: Shape) -> String =
  match s {
    Circle(r) if r > 100.0 => "巨大的圆"
    Circle(_) => "圆"
    Rect(w, h) when w == h  => "正方形"
    Rect(_, _) => "矩形"
  } // 穷尽 ✔；删掉最后一支则报错
```

### 3.3 无 null：Maybe / Result 内建

```vela
fn head(xs: [a]) -> Maybe a = xs[0]              // 越界返回 Nothing，不崩溃

fn first_even(xs: [int]) -> Result int ! overflow =
  match xs {
    [] => Err(not_found)
    [x, ..] when x % 2 == 0 => Ok(x)
    _                   => Err(not_an_even)
  }

fn port() -> int ! io =
  let n = first_even(args())?          // ? 传播 Err/效应，类型自动追踪
  io.print(n)
```

### 3.4 多态、约束与泛型记录

```vela
fn map<A, B, F: Functor f>(fa: f<A>, g: fn(A) -> B) -> f<B> = fmap g fa

fn stats(xs: [f64]) -> {mean: f64, sd: f64} =
  let m = mean xs
  { mean: m, sd: sqrt (mean (map (fn(x) => (x - m) ** 2.0) xs)) }
```

### 3.5 线性资源

```vela
fn count_lines(path: Path, sink: fn(File) -> a) -> a ! io =
  let f = open(path)                   // 线性：必须被消费或关闭
  defer f.close()                      // 作用域退出保证释放（编译期插入）
  loop over f.lines(): sink // sink 不可被调用两次fn bad(path: Path) -> int ! io =
  let f = open(path)
42                                   // ✘ 线性资源泄漏（编译错误）
```

### 3.6 代数效应与 handler

```vela
effect State s {
  get :: () -> s
  put :: (s) -> unit
}

fn tick(init: int) -> [int] ! {State int} =
  let xs = []
  for _ in 0..10 {
    let n = get()
    put(n + 1)
    xs.push(n)
  }
  xs

fn run(init: int, body: fn() -> a) -> a ! {} =
  handle body with handler State s = {
    get()       => (s, resume s)
    put(v)      => ((), resume v)
  }
```

**关键点**：effect handler 让"状态/异常/协程/随机/时间"都变成库而非语言魔法，同时 handler自身的效应行可被推断与组合。

### 3.7 结构化并发

```vela
fn crawl(urls: [Url]) -> [Doc] ! {io, net} =
  let chan = buffered[Doc](size = 4)
  workers = parallel_for (urls, workers = 8) { u in
    chan.send(fetch(u))?              // 消费一个线性 Send 权
  }
  chan.close()
  sort (chan.collect()) // 生命周期受结构约束
```

编译保证：并发任务不会逃逸其父作用域；任何并行访问都通过 `Task`/`Chan` 的线性能力，**不存在数据竞争的定义域**。

### 3.8 管道与宏（可选糖）

```vela
docs
  |> map(fetch)
  |> filter(is_valid)
  |> sort_by(score)          // 反管道糖：sort_by(score, filter(is_valid, map(fetch, docs)))

macro trace(x) { io.println("eval: " ++ quote(x)); x }
```

---

## 四、类型系统

### 4.1 基础

```
τ    ::= a | int | f64 | bool | String | unit | τ -> τ                                  (全函数，隐式一等公民)
      | [τ] | {l : τ, ..}                        (同构数组 / 记录类型)
      | τ | τ                                    (和类型)
      | μa. τ                                   (递归类型，如 [τ])
      | forall a. τ                              (全称量化)
      | exists a. τ
      | {E1, E2 | ρ}                              (开放效应行)
```

- **推断**：双向类型检查（先合成、后双向），HM let-多态（Monotone + relaxed value restriction），局部 let 可特化。
- **记录**：行多态，字段访问 O(1)，结构宽度亚类型。
- **GADT**：`type Expr a = Lit(a) | Add(Expr int, Expr int) if a ~ int`，支持类型驱动分派。
- **约束集**：`+ (a ~ int, Ord a)`，在编译期静态求解；数值塔默认 `Num {i8..f64}`，溢出检查可配置为回绕/检查/提升。
- **内建细化的轻量依赖类型**：`type Nat = int where x >= 0`、`type Vec n a = {len: n | n >= 0, ..}`，索引 `xs[i] : a where0 <= i < xs.len` 在层式检查中自动应用。

### 4.2 效应系统（核心创新点之一）

```vela
fn f(x: int) -> int ! {io, log, net}
fn g(x: int) -> int ! {io, net}        // 调用 f 后效应收窄
```

- 效应推断自底向上，签名是**契约上界**；实现里若效应 ⊆ 声明，编译通过（"效应多态收敛"）。
- `pure` 是效应行的单位元 `{}`，所有不写 `!` 的函数在类型上就是纯的（可被编译器验证并优化）。
- **可处置性 (disposal)**：`log` 是 `disposable`，`io` 是 `undisposable`，两者在 handler 边界被静态检查，避免把一次性资源捕获到 handler 之外。
- `?` 运算符把 `Result`-style 失败与效应提升合并，`try/handle` 显式捕获。

### 4.3 线性与唯一类型

- `unique T`：至多一次移动，零次须显式 `drop`。
- `fn T -> T`：**借用**（调用者可继续使用）；`! fn T -> T`：独占移动。
- `Send` / `Sync` 是可求解的自动约束，由模块边界与并发 spawn 点检查。
- 默认值不线性；若 `T` 含线性字段则记录整体线性（自动线性化）。

---

## 五、语义与运行时保证

| 保证 | 实现方式 |
|---|---|
| **尾调用消除** | 全语言强制尾位置标注，CPS 中间表示保证 100% 尾调用优化（深递归不爆栈） |
| **无未定义行为** | 无裸指针（FFI 区除外）、无 UB、无整数未定义溢出（回绕也明确定义） |
| **求值顺序确定** | 严格（call-by-value），从左到右，ADT 构造严格、模式匹配惰性求值绑定 |
| **强规范化于安全子集** | `let`-多态 + 强类型的纯子集可类型判定终止，模式匹配无嵌套模式求值器简化 |
| **确定性随机/时间** | 随机与时钟只能通过 handler 注入，纯代码在同一环境下可复现 |
| **无全局可变状态** | 单例只能由 `effect Global` 的能力句柄持有 |

---

## 六、编译管线

```
源文件
  ↓ ① 解析（可省略分号）＋ 布局恢复
  ↓ ② 宏展开（卫生，defsite）
  ↓ ③ 脱糖：管道/推导/for/推导式 → 核心语言
  ↓ ④ 双向类型检查 + 效应推断 + 线性/并发/穷尽性/终止性分析
  ↓ ⑤ 模式匹配编译（决策树 + 默认拒绝分支）
  ↓ ⑥ ANF / SSA构造（和类型消解：tag + 字段向量）
  ↓ ⑦ 优化：内联展开、迭代器融合、case-of-case、η-展开、外化标注、引用计数化(线性值)
  ↓ ⑧ 单态化（约束实例化）→ 逃逸分析 → LLVM IR ─┐
                                                   ├→ 代码生成（重定位）
  ↓ ⑧b 字节码 VM（编译到 .vec，栈式+tag，解释/JIT）─┘
```

**运行时**：约 1500 行 Rust/C。提供：
- 可插拔 GC（默认标记-清扫分代，或手动/引用计数用于线性子集）；
- 无 GC模式：所有分配显式 `arena`，用于嵌入式与 WASM；
- 线性堆：内联释放指令，`defer` 编译为 scope guard；
- 纤程（1 KB 栈）供 handler 与结构化并发使用。

**目标性能**：热路径与 Rust/C 同数量级（内联+融合后无中间分配）；启动时间 < 8 ms（字节码）。

---

## 七、模块系统与工具链

```vela
module net.http as http                  // 能力授予
import std.io as io (read_file, println)
import prelude.{Map, List} hiding (head)
```

- **能力式导入**：模块导出函数时可以标注所需效应；跨包调用若引入未声明效应，编译报错（而非运行时才炸）。
- **可见性**：`pub` / `pub(crate)` / `pub(module X)`；私有项不参与外部穷尽性检查（封闭/开放 ADT 标记）。
- **包管理**：`vpkg` —— 单一锁文件、能力图校验、确定性构建、内容寻址缓存。
- **工具链**：`velac`（编译）、`vela fmt`（格式化，风格唯一）、`vela doc`（从注释生成文档）、`vela check`（零生成 LSP）、`vela test`（属性测试 + 示例测试内建）、`vela bench`。

---

## 八、标准库概览

```
prelude   List / Option / Result / Either / Vec / String / Map / Set / Tuple
numeric整数与浮点（显式提升）、任意精度整数、定点数、Rational、复数
text      Unicode 感知的分段/大小写/正则（线性时间保证，无回溯爆炸）
parse 解析器组合子（backtracking，融合）
effect    State / Reader / Writer / Except / Trace / Random / Time / Async
io        文件 / 终端 / 编码 / 缓冲区（全部线性句柄）
net       TCP / TLS / HTTP（effect `net`，句柄线性）
sys       受限不安全区（指针、内联汇编、FFI）——唯一需要 `unsafe` 的地方
```

FFI 规则：外部函数默认视为**未净化**（可能做任何事），其效应必须全量声明；编译器据此生成正确性论证可用的边界。

---

## 九、示例：一个手写 JSON 解析器（展示融合 + 穷尽性）

```vela
type Json =
  | Null
  | Bool(bool)
  | Num(f64)
  | Str(String)
  | Arr([Json])
  | Obj([(String, Json)])

fn parse(s: String) -> Result Json ! {} =
  let (v, rest) = value(skip_ws(s))?
  match rest { [] => Ok v, _ => Err(trailing(rest)) }

fn value(s: [Char]) -> Result (Json, [Char]) =
  match s {
    ['{', ..] => object(skip_ws(tail s))
    ['[', ..]        => array(skip_ws(tail s))
    ['"', ..]        => do { let (v, r) = string(s); Ok (Str v, r) }
    ['t', 'r', 'u', 'e', ..] => Ok (Bool(true), drop4(s))
    ['n', 'u', 'l', 'l', ..] => Ok (Null, drop4(s))
    [c, ..] if is_digit(c) or c == '-' => number(s)
    _                                     => Err(expected_value(s))
  }
```

**编译器保证**：所有匹配穷尽（编译器生成的"不可达分支"警告）；`Str v` 等构造强制复制-移动语义；解析器链无堆分配中间列表。

---

## 十、相对于现有语言的差异化

| 维度 | Haskell | OCaml | Rust | Scala 3 | **Vela** |
|---|---|---|---|---|---|
| 效应 | 无（需框架级抽象） | 有限 handler | 无（Result + ?） | 无（Future/side effect） | **类型级、可推断、可组合的开放行** |
| 资源 | 无约束 | 无约束 | 线性/所有权 | 线性 | **线性 + 借用 + handler 边界处置性** |
| 空安全 | Maybe | Option | Option | Option | **无 null，`Maybe` 内建且穷尽** |
| 终止性 | 需注解 | 需注解 | 借用检查间接保证 | 不保证 | **默认检查全函数性，`partial` 显式标注** |
| 模式匹配 | ✔ | ✔ | ✔ | ✔ | ✔ + **类型驱动分派 + 记录/元组嵌套解构** |
| 并发安全性 | 需手动 | 需手动 | 类型系统保证 | 需手动 | **类型系统保证（线性能力）** |
| 性能控制 | GHC 较重 | 较好 | 最优 | 较好 | **LLVM 路径 + 无 GC 模式 + 融合迭代器** |

**真正新的三件事**：
1. **效应行 + 线性类型的联合推断**：资源与副作用在同一套静态检查中相遇（例如 handler 捕获 `unique` 资源时报错，报告精确到 effect 操作）。
2. **全函数性作为默认检查**：把"程序会不会挂/死循环"从测试问题变成类型问题。
3. **能力式模块 + 结构化并存的统一**：模块权限即能力，跨边界无法绕过；配合线性类型得到无竞争的编程模型。

---

## 十一、实施路线

| 阶段 | 里程碑 |
|---|---|
| **M0（3 个月）** | 核心语言（无 handler）：HM推断、ADT、模式匹配、线性子集、闭包编译（闭包转换 + 词法作用域分析）、VM |
| **M1（3 个月）** | 效应行推断与 `?`、`Result/Maybe`、穷尽性与全函数性检查、`open` ADT |
| **M2（3 个月）** | 代数效应 handler、纤程、结构化并发、线性堆与 `defer` |
| **M3（3 个月）** | LLVM 后端 + 融合优化、`vpkg`、LSP/formatter/test |
| **M4** | 增量编译/并行类型检查、内容缓存、自举（用 Vela 写部分编译器前端与标准库） |

---

## 十二、可证伪的设计赌注

> **赌注**：如果把"效应、失败、资源、终止性"全部写进类型，并让编译器把它们都检查掉，那么纯函数式语言的主要工程阻力（可维护性、跨语言 FFI、性能、并发正确性）会同时下降80%。

**验证方法**：M1 结束时实现一个 5000 行的真实服务（爬虫/JSON 处理 + 并发 IO），与 Rust、Elixir、Haskell 基线对比：缺陷率、编译期捕获的 bug 数量、运行性能、二进制体积、团队的"非函数式背景者上手时长"。

---

**一句话总结**：Vela = Rust 的资源安全 × Haskell 的抽象能力 × ML 的可预测性，把所有危险都搬进类型里，让运行时只剩"按声明行事"这一件事。
