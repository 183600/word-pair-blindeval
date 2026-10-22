# [rerun:space-bunny-free] 任务1 函数式编程语言 | 条件: baseline | 第 5 次

**Prompt:** 设计一个全新的函数式编程语言

**耗时:** 52.3s | **tokens:** 196/9634(推理 4811) | **finish:** stop

---

# Mote —— 一门为「可组合的效应」而生的函数式语言

> **一句话**：Mote 是一门纯函数式、**总量（total）**、**静态效应追踪**（行多态）并内置**代数效应处理器**的语言；它没有 null、没有异常、没有可变变量、没有未检查的递归，而所有这些能力（IO、状态、异常、异步、事务）都是标准库里约 300 行基于 effect handler 的普通函数。

---

## 一、设计原则（6 条）

| # | 原则 | 含义 |
|---|---|---|
| 1 | **一切皆不可变值** | 无 `let mut`、无数组指针算术、无 null；`Option`/`Result` 必须显式处理。 |
| 2 | **效应写进类型** | `fn (Int) -> Int ! {Log, Fs}`：不能悄悄做 IO，读文件在类型里看得见。 |
| 3 | **所有递归都必须终止** | `rec` 只接受结构化递减递归 + 互递归 SMT 证明；匹配必须穷尽。于是每个函数都有语义良好的不动点。 |
| 4 | **模式匹配是一等公民** | `match` 是表达式，**子句可以被抽出来当函数组合**；编译器强制穷尽，杜绝 `if/else` 泥潭。 |
| 5 | **核心极小，库极大** | 内建语法只有 8 个构造；数组、map、promise、循环全部是可复用库函数。 |
| 6 | **双向检查 + 渐进边界** | 本地全推断，边界需签名；FFI 值默认为 `dyn`，跨边界必须显式 `coerce`。 |

**明确拒绝**：宏（用高阶组合子代替）、运算符重载（用函数名代替）、隐式数值转换、猴子补丁、全局可变状态、`goto`。

---

## 二、名字与形态

*扩展名 `.mote`，包管理器 `mote`，构建产物 `*.mo` / 可执行文件。
* 前端：手写递归下降解析器 → AST；后端：解释器（快速迭代）+ LLVM 后端（生产）。
* 编译模型：闭包转换 + **单子 IR**（效应被编译成 `E f k` 的 CPS 风格中间表示），handler 编译成 `reset/shift` 对。

---

## 三、语法速览

```mote
// ── 模块 ───────────────────────────────────────
module Shape

//变体
type Shape =
  | Circle(Float)
  | Rect(Float, Float)

// 记录：不可变，更新是"复制+覆盖"
record Point = { x: Float, y: Float }

// 类约束（只有静态派发，无实例字典泄漏）
class Show a where
  show : a -> String

// 函数类型即箭头，可省略外层括号
area : Shape -> Float
area = fn s -> match s {
  Circle(r)   -> 3.1415926 * r * r
  Rect(w, h)  -> w * h
}

// 列表推导：编译成 handler + 组合子，不是特例语法
squares = { x * x | x <- [1, 2, 3], if x != 2 }

// 记录更新、管道、字符串插值
move p dx = p & { x = p.x + dx }
scaleAll s k = map(move(_, s) | p <- pts) // 占位符：下划线
banner name = "你好，\{name}！共 \{pts.len} 个点"

// 一等子句抽取：把 match 的分支列表当成高阶数据
dispatch : fn (Shape) -> String
dispatch = clauses([
  Circle(_) -> "圆",
  Rect(_, _)-> "方"
])
```

### EBNF（节选，完整约 60 行）

```ebnf
Program = ModuleDecl* ;
Decl       = TypeDecl | Bind | SigBind ;
Bind       = "let" Rec? Pattern "=" Expr ";" ;
SigBind    = Pat ":" Type ;
Type       = Arrow | App ;
Arrow      = Type "->" Type | Type "!" "{" EffRow "}" "->" Type ;
TypeDecl   = "type" CapId ("=" Constructor ("|" Constructor)*)? ";"
 | "record" CapId "=" "{" FieldDecl* "}" ";" ;
Expr       = Let | Match | Handle | If | Fn | Pipe | Bin | Lit | App | Var ;
Match      = "match" Expr "{" Clause+ "}" ;
Clause     = Pattern "->" Expr ;
Handle     = "handle" ("deep" | "shallow")? Expr "{" HClause+ "}" ;
HClause    = lowerId Params "k" "->" Expr ;
Expr       = "{" (Pat "<-" Expr) ("," Pat "<-" Expr)* ["," "if" Expr] "}" ; (* 推导 *)
```

---

## 四、六个关键设计

### 1. 模式匹配：一等公民 + 穷尽性强制

```mote
describe : Option<Option<Int>> -> String
describe = fn o -> match o {
  None          -> "空"
  Some(None)    -> "有空的可选"
  Some(Some(n)) -> "有值 \{n}"     // 编译器证明：这三个子句穷尽
}
```

* 穷尽性在**类型检查期**做（不完整模式即编译错误，报错给出缺失构造子）。
* 子句可以被**抽出、组合、传递**（`clauses([...])`），因为它就是 `Pattern -> Expr` 的列表。
* 编译器把 match 编译成决策树 + 跳转表；模式支持 `as`、守卫 `if`、区间 `1...9`、字面量、结构绑定、列表 `init, ..rest`。
* **副作用**：因为模式穷尽，语言里可以安全地做**数据驱动的 DSL**：把「解析 + 类型检查 + 代码生成」写成一串子句。

### 2. 效应系统：行多态 + 子效应

```mote
effect Log =
  | log : String -> Unit

effect State<T> =
  | get : Unit -> T
  | put : T -> Unit

//效应行变量 r出现在类型里
zipWith : (fn (A -> B) ! e) -> (fn (A -> B) ! e) -> (fn (A -> C) ! e)
zipWith f g = fn a -> handle f(a) {
  _ op xs k -> k(map(g | x <- xs)) // 转发所有操作，重写结果
}
```

* 效应集合是**开放行** `{Log, State<Int>, e}`，行变量可被特化。
* 效应有**子类型**：`{Log} ⊆ {Log, Fs}` ⇒ 纯函数可以冒充会 IO 的函数使用（反向由 `unsafe` 强制）。
* 效应可**多态**：`(fn () -> A ! e) -> A ! e` 这类 `lift` 由推断自动插入。
* 拒绝效应，但要在函数内部用：`in !{} do ... end`（显式擦除），必须函数签名本身为空效应。

### 3. 代数效应处理器：IO 只是库

```mote
// 一个"带日志的状态计数器"，源码里没有一行 let mut
counter : Unit -> Int ! {State<Int>, Log}
counter = fn -> handle run(unit) {
  put(10) k            -> k(unit)
  get k -> k(7)          // 忽略 continuation：提前返回
  log m k              -> { println(m); k(unit) }
} {
  get k -> { let v = 17; k(v) }        // 未处理的操作向外传播
  put v k -> k(v)
}

// 把浅层 handler 组合成栈，等价于中间件
program = counter |> withLog |> withState(0)
```

* 提供 `shallow`（默认，一次性）与 `deep`（对 continuation 重复执行做处理）两种处理器，`shift/reset/control` 保留为显式可用的原语。
* **处理器帧不可逃逸**：编译器禁止把 continuation 存进数据结构，杜绝「多次调用导致的不一致性」这个代数效应最大的坑。
* `try/catch`、事务（`withTx`：失败自动回滚）、`Async/spawn`、`Res/Timer`（确定性析构）全部是库里约 300行的 handler。
* **`do` 记法是可选语法糖**，可整文件禁用（`#lang strict`），禁用后仍编译到同一核心 —— 编译器保持诚实。

### 4. 总量性与递归

```mote
sum : List<Int> -> Int
sum = rec fn xs -> match xs {
  []           -> 0
  [x]          -> x
  [x, ..rest]  -> x + sum(rest)      // 必须结构递减
}

length : List<a> -> Int
length = rec fn xs -> match xs { [] -> 0; [_, ..r] -> 1 + length(r) }
```

* 归纳关系可以是**用户定义的代数数据类型**（如 `Nat`、`Tree`），也可来自索引（sized types 的简化版：`Vec<a, n>`，保证 `head` 安全）。
* 变长循环不是语法，而是库函数：
  ```mote
  repeat(10, fn i -> println(i))            // index 递减可验证
  whileRange(0, n, fn i -> …)                // 或 via Fixpoint/共递归
  ```
* 互递归终止性用轻量 SMT（大小 / 度量 `->`标注）判定，判不了就要求 `rec` 显式声明并降级为运行时检查警告。

### 5. 双向类型检查 + 渐进边界

```mote
let f x = x + 1                 // 推断为 Int -> Int  （局部全推断）
val g : fn (a) -> a -> Int      // 顶层必须有签名（可读性 + 编译速度）
```

* 内部用**双向 + 唯一类型 +不可变行**（HM 的行多态扩展），避免多态子类型带来的不可判定推断。
* FFI 边界：
  ```mote
  import "libcrypto" as C // 所有导出 : dyn
  let h = C.sha256 |> coerce(SHA256)   // 显式、可搜索、可标注
  ```
  `coerce` 处插入运行时形状检查；`dyn` 不能出现在非边界位置（可 `#trusted` 逃逸，但有 lint）。
* 错误信息是**一等设计目标**：每个错误给出「无法匹配两侧 + 期望 + 实际 + 是否只是效应不一致」。

### 6. 模块与 trait

```mote
module List {
  map   : (fn (a -> b)) -> List<a> -> List<b>
  foldL : (fn (b -> a -> b)) -> b -> List<a> -> b
}

instance Show Shape where
  show = fn s -> match s { Circle(r) -> "C(\{r})"; Rect(w,h) -> "R(\{w},\{h})" }
```

* 无 `where`、无实例字典泄漏、**只有一个全局求解器**，实例查找是确定的（无 C++/Rust 那样的重叠歧义）。
* 数值塔（`Int/Float/Rational`，`class Num`）由类实现；**无隐式转换**，`->` 里的 `Int -> Float` 需 `f64(x)` 显式。

---

## 五、类型系统形式化（骨架）

```
t ::= x | τ | τ1 -> τ2 ! ε | τ1 × … τn | Σ c_i(τ_i) | ∀α<q. τ | τ?
ε ::= {} | e, ε | ε1 ∪ ε2 | ρ(row var)          -- 行，无重复，子类型子集

Γ ⊢ e ⇒ τ ! ε                                 (合成)
------------------ (T-App)   ----------------------------------
Γ ⊢ e ⇒ fn τ1 -> τ2 ! ε        Γ ⊢ e1 ⇐ τ1      Γ ⊢ e2 ⇒ τ2 ! ε'
--------------------------------------------------
Γ ⊢ e1 e2 ⇒ τ2 ! (ε ∪ ε')

Γ ⊢ e ⇐ fn τ1 -> τ2 ! ε                        (检查，含效应子集 sub-typing)
```

处理器的规则（关键在结果行收缩）：

```
Γ ⊢ e ⇒ τ ! (o(τa), ε)         Γ, k : τa -> τ ! ρ , y:τb ⊢ c_i ⇒ τb ! ε_i
∀i. Γ ⊢ c_i ⇒ τb ! ε_i,   τb = τ, ε_i ⊆ ρ ,  y ≠ k
--------------------------------------------- (T-Handle)
Γ ⊢ handle e { c_i } ⇒ τ ! (ε \ o)     -- 若 y : τ 未被使用，则 τ <: τb
```

*内部编译到带 `eff` 标注的 ANF/CPS IR：`E(λx. cont. body, handler-table)`。
* `deep` 处理器的 continuation 检查额外要求「无歧义重放」，编译器插入 `replay guard`。

---

## 六、三个完整示例

### 1. 解析器组合子（模式匹配的正当用途）

```mote
parser Json =
  rec fn txt ->
    skip(space, txt) >>=
    (fn t ->
      dispatch([
        ['{', ..r] -> obj(r)   .>> skip(space, _) >>= wrap(_ => object),
        ['[', ..r] -> arr(r)   .>> skip(space, _) >>= wrap(_ => list),
        [c, ..r]   -> if c == '"' then string(r) else num(r)
      ])(t))
```

### 2. 异常安全的资源管理

```mote
effect Res = | open : Text -> Handle | use : Handle -> A -> Unit | close : Handle -> Unit

readConfig : Text -> Text ! {Res, Throw, Log}
readConfig = fn path -> { h <- open(path); defer(close, h); use(h) }

main = readConfig("/etc/app")
      |> withResource // 即使 use 抛错，close 必被调用
      |> try(recover = fn _ | ioErr -> "fallback")
      |> withLog(levels = {warn, error})
      |> runTop```

`defer` 是 `Res` effect 的一等语法糖，保证释放**恰好一次**且不依赖异常 —— 这在纯函数语言里第一次变得自然。

### 3. 并发：把 `Async` 当普通 effect

```mote
effect Async =
  | await : Job<a> -> a
  | spawn : (fn (Unit -> a ! {Async, e})) -> Job<a>

pipeline = fn xs ->
  jobs = { spawn(fn -> heavy(_)) | x <- xs }
  handle awaitAll(jobs) { await k j -> k(result(j)); _ op a k -> k(a) }
```

用户代码里没有 `async/await` 关键字，编译器也不需要内建协程 —— `Async` handler 在解释器/后端里就是一个 fiber 表。

---

## 七、与现有语言的对比

| 维度 | Haskell | OCaml | Elixir | Rust | **Mote** |
|---|---|---|---|---|---|
| 效应可见性 | 靠约定/扩展 | 无 | 隐式进程 | 显式但侵入式线程 | **类型里，行多态** |
| 不变性 | 纯 | 大量可变 | 可变进程 | 需 `mut` | **强制纯，例外仅在 handler帧内** |
| 终止性 | 无保证 | 无保证 | 无保证 | 借用期 | **编译器保证（总量）** |
| null | 无 | 有 | `nil` | `Option` | **无** |
| 状态/IO/异常来源 | 语言 + 库 + 扩展 | 语言内建 | 语言内建 | 语言内建 | **全部 =库里的 handler** |
| 模式匹配 | 强 | 强 | 弱（`case`） | 强 | **强 + 一等子句 + 穷尽** |
| 推断 | 完整 HM+类 | 完整 | 无 | 无 | **局部全推断 + 边界签名** |
| 宏 | 有 | 有 | 有 | 有 | **无（用组合子）** |

**真正的差异**：把「不纯的东西」全部降级为**普通函数的参数与返回值**，而把这些函数的**签名写在类型里**；编译器保证这些函数无法互相逃逸，于是它们可以自由组合而不产生代数效应的经典陷阱。

---

## 八、标准库骨架

| 模块 | 内容 |
|---|---|
| `Prelude` | `Option/Result/Either`、二/三/五元组、恒等、组合子、`assert` |
| `List` | 10 个以上纯列表函数 + `View`（惰性头尾视图，用于零分配迭代器） |
| `Seq` | `Lazy` 序列、`iterate/cycle/repeat`（均为代数效应实现） |
| `Map/Set` | 平衡树 / HAMT；`group/sort/unique` 组合子 |
| `Text/Bytes` | UTF-8 不可变切片 + 内建 `\{}` 插值 +简单的 `format`（无 printf 类型体操） |
| `Eff` | handler 组合子：`compose / retry / timeout / withResource / withState` |
| `IO/Fs/Net/Clock/Random` | 全部基于 `effect`，可在纯函数测试中替换为 mock handler |
| `Test` | `property` 缩窄（QuickCheck）、`snapshot`、`expect` |
| `Num/Rat` | 数值塔、精确有理数、任意精度整数 |

**测试友好的副产品**：因为 IO 是 handler，`main` 就是 `runTop(main)`，单元测试时把 `runTop` 换成 `runMemory` 即可拿到**全内存的确定性测试**。

---

## 九、实现路线（团队3 人，约 18 个月到1.0）

| 阶段 | 周期 | 交付 |
|---|---|---|
| 0 原型 | 0–2 月 | 解析器 + AST解释器 + HM推断，无效应 |
| 1 模式与类 | 3–4 月 | 决策树编译、穷尽性检查、实例求解器 |
| 2 效应系统 | 5–8 月 | 行多态推断、`{ }` 子类型、诊断信息 |
| 3 代数效应 | 9–12 月 | `handle` 深浅层、effect IR、编译期「帧不可逃逸」检查 |
| 4 优化后端 | 13–16 月 | LLVM/闭包转换+逃逸分析、CPS 优化、GC（分代 + 增量，或可选无 GC 手动 arena） |
| 5 生态 | 17–18 月 | 包管理器、`mote build --release`、FFI、Language Server、格式化器 |

**关键实现杠杆**：行多态推断用「效应行归一化 + 单一主约束（like OCaml 的 row unification）」；类约束求解用**单一全局静态查找**（无重叠），保证可判定。

---

## 十、风险与缓解

1. **效应系统 + 类 + 双向 = 复杂度过高？**
   *缓解*：强制「子集原则」。核心只有 `let/match/fn/|>/if/handle/type`；先做交集类型（simpler）的实验版本，再上行多态。
2. **错误信息是生死线**：多态 + 效应 + 类的组合会让报错灾难化。
   *缓解*：诊断引擎单独设计（约束级别归因、效应差异单独高亮、所有错误提供 `#mote:explain` 展开）；把 60% 精力花在「3 条内说清哪里错了」。
3. **代数效应的 continuation 逃逸**：语言陷阱，不只是工程问题。
   *缓解*：类型级禁止（上面第 3 节），并禁止 `dyn` 携带 `!`效应跨越 handler边界。
4. **性能感知问题**：handler 链可能退化成 CPS 噩梦。
   *缓解*：一阶 handler（`withState/withLog` 模式下）特化编译为直接调用；`deep` 才走完整 CPS；提供 `-fhandler-inlining`。
5. **没有宏 → 系统编程/DSL 表达力受限？**
   *缓解*：提供**受控的编译期插件**（Rust/Python 写的代码生成器，输入是 AST 而不是源码文本），保证卫生性。

---

## 十一、如何判断这门语言是否成功（可证伪指标）

* **指标1（表达力）**：用 20 个真实小任务（JSON 解析器、CSV、TCP echo、Lua 解释器、编译器 pass链…）对比 OCaml / Elixir / Kotlin，人力时间中位数是否 ≤ 60%。
* **指标 2（可学）**：新人 48小时内写出「带 IO + 状态 +异常处理的 CLI」的比例 ≥ 80%；错误信息导致的时间占比 < 15%。
* **指标 3（性能）**：微基准（n-body、树遍历、字符串处理）中位性能达到 OCaml 0.8×、Rust 1.2×。
* **指标 4（设计质量）**：预注册的核心库（`Eff`、`List`、`Map`）源码中，`!` 效应标注不超过 5 处；一旦超过，说明效应系统泄漏，需回头修设计而不是加逃生舱。

---

### 附：一段能跑起来的「Hello Mote」

```mote
module Main

effect Greet = | greet : String -> Unit

greetTwice : fn () -> Unit ! {Greet}
greetTwice = fn ->
  for i <- 0...2 do
    greet("你好，第 \{i} 次")

main = handle greetTwice() {
  greet msg k -> { println(msg); k(unit) }
}
```

*无需 `let mut`，无需 `for` 的变量可变，无需 `try`，无需 `I/O` 特权——因为 `Greet` 是被参数化的效应，`handle` 就是一个普通函数。**这就是 Mote 的全部主张。**
