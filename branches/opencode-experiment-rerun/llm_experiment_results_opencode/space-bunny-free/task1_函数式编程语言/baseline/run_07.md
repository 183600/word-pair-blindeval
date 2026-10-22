# [rerun:space-bunny-free] 任务1 函数式编程语言 | 条件: baseline | 第 7 次

**Prompt:** 设计一个全新的函数式编程语言

**耗时:** 55.2s | **tokens:** 196/7164(推理 2232) | **finish:** stop

---

# 设计一门全新的函数式编程语言：**Lume（流明）**

> 定位：静态强类型、面向现代工程的通用函数式语言。
> 口号：**"一切皆表达式，一切效应皆在类型中。"**

---

## 一、设计目标与取舍

| 目标 | 具体承诺 |
|---|---|
| 正确性 | 无 `null`、无未定义行为、穷尽性检查、显式效应 |
| 可推理性 | HM 推断 + 行多态；无需写类型也能过大型项目 |
| 性能 | 激进内联、无装箱、尾调用保证、`effect` 不付运行时代价 |
| 工程性 | 模块/包管理、统一格式化、LSP、增量编译、LLVM 后端 |
| 学习曲线 | 语法对熟悉 JS/Python 的人 1 天上手，对 ML/Haskell 的人 2 小时上手 |

**刻意不做的**：面向对象继承、隐式类型转换、可变循环变量、异常、宏（首版）、`null`、未检查的下标访问。

---

## 二、名字与自然语法

*变量/函数：`camelCase`，构造器/类型：`PascalCase`
* **缩进敏感**（2 空格），与 Python 一致但语义严格（避免"空格猜类型"）
* 注释：`// 行`，`/* 可嵌套块 */`
* 关键发明：**占位点 `.`** 与 **管道 `|>`**，让函数组合像数学一样顺

```lume
module Analytic

// 类型签名可选（签名与实现会互相校验）
let area : Shape -> Float
let area sh = match sh
  Circle r -> 3.14159 * r * r
  Rect w h            -> w * h
```

---

## 三、词法与操作符（完整优先级表）

| 优先级 | 操作符 | 结合性 | 说明 |
|---|---|---|---|
| 10 | `::` | 右 | 列表构造 |
| 9 | `^` | 右 | 字符串/列表拼接（避免 `++` 的歧义） |
| 8 | `*` `/` `%` | 左 | 整数除 `/` 向下取整，`div` 显式除零报错 |
| 7 | `+` `-` | 左 | |
| 6 | `==` `!=` `<` `<=` `>` `>=` | 左 | **无重载歧义**：都是 `Ord` 能力约束 |
| 5 | `&&` `\|\|` | 左 | 短路 |
| 4 | `\|>` `<\|` `>>` `<<` | 左 | 管道 / 组合子 |
| 3 | `$` | 右 | 低优先级应用 |
| 2 | `:::` | 右 | `f ::: g` = `g . f` |
| 1 | `as`、`is` | — | 模式判定与向下转型 |

核心语法糖：

```lume
xs |> filter (. > 3) |> map (. * 2) |> sum
// 等价于 sum (map (\x -> x * 2) (filter (\x -> x > 3) xs))
```

`.` 是"**参数占位符**"：在一个函数内部，`.` 代表当前正在传给外层函数的参数，`map (. * 2)` 与 `map (\x -> x * 2)` 完全同义。这消除了 ML 系语言里 `(\x -> x + 1)` 的视觉噪音。

---

## 四、类型系统

### 4.1 基础

```
Type := Var | Con Int | Arrow | Forall | Record | Row | App
Arrow := A "->" B
```

* **HM 类型推断** + **数字字面量多态**（`3` 推成 `Int`，在需要时多态提升）
* **记录类型结构化子类型**：`{ x : Int, y : Int } <: { x : Int }`，无需类型类
* **唯一化 + 类型类**：需要多态行为时才写约束，且**实例解析发生在推断之后的 elaboration 阶段**（避免 Haskell 的推断歧义）

```lume
let maxBy cmp xs ys =
  let go (best : a, rest : [a]) = match rest
    []      -> best
    y :: t  -> go (if cmp y best > 0 then y else best, t)
  go (head xs, tail xs)

// 调用处零成本：cmp 被内联特化（"静态分派"），无需字典对象
```

### 4.2 效应系统（Effect Rows）

这是 Lume 的核心。**函数类型携带自己可能触发的效应**：

```
Pure a = a
Eff e a = () -> (e, a)        -- 内部表示：类型里的零元函数
```

```lume
type Effect[a] = { ! io, ! fail E, ! state S, ! env }
```

三个层次：

1. **无标记**：`pure`（默认）
2. **无能力**：`throw x` 提升为 `E ! { throw E }`（类似 Koka）
3. **有参数能力**：`get : () -> A ! { state S }`（效应可携带数据 → 代数效应）

```lume
let readAndReport : Effect[Unit]
let readAndReport = do
  let line <- readLine "输入：" // 隐含 ! io
  let n    <- parseInt line            // ! { io, fail String }
  print ("你输入了 " ^ show n)
```

### 4.3 推断示例（含步进）

```lume
let compose f g x = f (g x)
```

```
t0: ?a -> ?b -> ?c (x)
t1: ?c -> ?d (f . g)
t2: ?d -> ?b                   (f (g x))
unify ?c =? ?c -> ?d ⇒  ?c = t1, ?a = ?d
结果: (?b -> ?c) -> ?c -> ?b
```

行多态统一（Koka/Leijen 的"行变量 + 缺少标签"规则）：

```
{id io | α} ∪ {io, fail E | β} =? {io | γ}   ⇒  γ = {fail E | β}
```

推论：调用有 `!io` 的函数后，局部 `let` 会自动把它并入外层；**不需要 `do` 记法也不会漏报效应**。

---

## 五、数据类型

```lume
// 代数数据类型（ADT）
enum Tree[T]
  | Leaf
  | Node(left : Tree[T], value : T, right : Tree[T])

// 记录 / 结构体
struct User =
  id    : Int
  name  : String      -- 可选字段用 ? 前缀
  email : ?String

// 具名参数构造（记录）
let u = User(id = 1, name = "Ada")

// 构造器省略
let mk x = Node(left = Leaf, value = x, right = Leaf)
```

**没有数组下标越界**：`xs[i]` 在编译期需 `bound = len xs` 约束（来自 `Vec` 的依赖类型切片），或者用 `xs.at(i) : Option[T]`（`.at` 走穷尽匹配）。字符串索引用 `charAt : String -> Int -> Char`，`bounds check` 由证明义务承担 —— 首版提供内建 `assert (i < len s)` 细化而不做完整 Dependent Types。

---

## 六、模式匹配

Lume 的模式匹配是**唯一构造序列化的机制**（无 `if let`、无 `try/catch` 的模式版本）。

```lume
let describe : [Token] -> String
let describe ts = match ts
  []                       -> "empty"
  [single]                 -> "one: " ^ show single
  [a, b, rest] if a == b  -> "pair " ^ show a ++ " +" ^ show (length rest)
  (Token :: _) :: (Token :: _)
 -> "two consecutive tokens"
  _                        -> "many"
```

支持：

| 类别 | 语法 |
|---|---|
| 构造器 | `Some x`、`Node(Leaf, v, Leaf)` |
| 字面量 | `0`, `-1`, `"s"`, `'c'`, `true` |
| 区间 | `1 ..= 9` |
| 或 | `Some x | Right x` |
| 嵌套 | `Some (Ok v)` |
| 列表/变长 | `[a, b, .., last]`、`(x :: _)` |
| as模式 | `n as whole` |
| 守卫 | `x if p` |
| 穷尽性 | 编译期检查，报告缺失的构造器**路径** |

穷尽性诊断示例：

```
error[E0043]: non-exhaustive patterns ↓
 7 │ match tree │   ├─ Node(Leaf, _, _) -> 1
    │   └─ Node(_, _, Leaf) -> 2
    ╰──── missing: Leaf  (case 1 of 2)
note: add `Leaf -> _` or `Node(_, _, _)` arm
help: `Node(Leaf, _, Leaf) -> 0`
```

**实现**：Maranget 的"有用模式矩阵"算法，`O(m·n)`，构造器行号（每行给所有变量标注分支来源），因此诊断信息能精确指向位置。

---

## 七、控制流与惰性

```lume
// 表达式，无语句
let grade n =
  if n >= 90 then "A"
  else if n >= 80 then "B"
  else "F"

// 列表推导（多生成器 = 笛卡尔积，带过滤与投影）
let squares = [ x * y | x <- 1..10, y <- 1..x, (x + y) % 3 == 0 ]

// 遍历（desugar 成递归，无可变状态）
for (name, age) in users do
  print (name ^ " " ^ show age)

// do 记法（等价于基于 handler 的语法糖）
main = do
  let cfg <- loadConfig ()
  let data <- fetch cfg.url
  save data```

**严格求值为默认**（性能可预测），惰性显式化：

```lume
let fib = lazy {                       // thunk，可被 memo  0 -> 0
  1 -> 1
  n -> fib (n-1) + fib (n-2)           // 强制时才展开
}

let naturals : [Int] = 0 ..            // 无限
let primes  : [Int] = 2 |> sieve |> filter (. |> isPrime)

// 惰性结构上的模式匹配必须写守卫（编译期禁止无守卫的结构性拆解）
// —— 这条规则从类型上排除了"无限列表 × 非生产性递归"的死循环
```

**无惰性走火**：所有 `lazy` 值都被 GC 追踪；无限流的模式匹配在类型检查期要求 guard，因此**保持性由类型系统保证**（无用户可达的死循环，除非纯 `let` 递归且不消耗 → 那会被优化掉）。

---

## 八、错误处理 = 代数效应 + handler

**不设计异常**。三档错误策略，全部可组合、可静态推理：

```lume
// 1) 可恢复：Result
let div a b : Result[Int, String] = if b == 0 then Err "div by zero" else Ok (a / b)

// 2) 局部恢复：match / do 的 catch
let safeDiv a b = do
  r <- div a b
  match r
    Ok v  -> print ("=" ^ show v)
    Err e -> print ("oops: " ^ e)

// 3) 全局捕获：effect handler
let withFallback def handler = handle
  def
with
  effect Fail[E]:
    op raise(e : E) = resume (handler e)
```

**handler语法**：

```lume
let runState : (() -> A) -> S -> (A, S)
let runState init thunk = handle thunk with
  effect State[S]:
    get() = resume (store s)
    put(v : S)     = resume (v) . set store v
  effect State[S] / state := init
```

实现采用 **one-shot 线性 handler**（Racket/Haskell 5 的 row-polymorphic handler 方案）：每个 handler 只捕获它列出的操作，其余通过剩余效应行继续上浮。因此：

* `resume` 只允许一次 ⇒ 无重入、无异常语义歧义
* 多层 handler 嵌套零成本（就是闭包调用）
* 可实现 tracer、timeout、memo、事务回滚

```lume
let timed f x = handle (f x) with
  effect Timeout:
    op after(ms, k) = spawn (later ms (raise Timeout)) . k

let counted = handle comp with
  effect State[Ref[Count]]:
    op tick() = resume (modify store bump)
```

---

## 九、模块、包与工具链

```lume
module Data.Pipeline

import Std.{ List, String } // 只导入可用名
import Net.Http as HTTP            // 别名
import Std.Json (decode as parseJson) // 选择性导入

export { pipeline, Stage }

// 私有定义
struct Stage[A, B] = Stage(name : String, run : A -> Effect[B, Error])
```

* 一模块一文件，路径即命名空间（`module A.B.C` ⇒ `A/B/C.lu`），禁止循环依赖（编译期检测）
* 公开接口即类型，**隐式导出全部非 `private` 项**
* 包管理：`lup add netlib`，语义化版本，`lup.lock` 锁定
* 生态：C ABI 互操作（`extern "c" fn puts(s : Ptr) -> Int`）、WASM 目标、LLVM 后端

---

## 十、并发（结构化、无隐藏任务）

```lume
main = do
  let chan = newChan [Result[Int, E]]()      // 类型化信道
  let all = handle
    do
      let ws = [ spawn (fetch url) | url <- urls ]   // 结构化并发生成      let rs <- gatherAll ws                       // 等待全部，异常集合
      rs |> flatten |> traverse_ save
  with
    effect Collect[E]:
      op join(xs) = resume (gatherAll xs)
  all
```

* 所有 `spawn` 属于当前作用域，离开作用域自动 join/cancel（**无游离 goroutine**）
* `select`、超时、取消是标准效应，可被 handler 覆盖（便于测试）
* 类型系统区分 `Effect[a]` 与 `Concurrent[a]`（线性可复制能力）

---

## 十一、编译器实现

```
源码 .lu
  │
  ├─(1) Lexer（缩进 → INDENT/DEDENT token，行列溯源）
  ├─(2) Parser → CST（错误恢复：产出多个错误再统一报错）
  ├─(3) Desugar：点占位符 / for / do / 管道 → 核心 lambda calculus
  ├─(4) 名字解析：模块图 + 唯一化（每个标识符一个 unique name）
  ├─(5) 类型推断：HM + 行多态 + 能力类  │      · 统一算法：Cheney 数字标签 + 行变量的"缺少标签"规则
  │      · 效果推断：操作符标签与 handler 覆盖率检查
  ├─(6) 模式检查：可达性 + 冗余 + 穷尽性（模式矩阵）
  ├─(7) Effect 分析：handler 合法性、resume 一次、深度可判
  └─(8) Core IR → ANF → SSA（闭包转换 / 内联） → 优化 → 后端
          · 后端 A：Lume 解释器（快速启动 + 教学）
          · 后端 B：LLVM 17（类型擦除到 tagged pointer，int装箱逃逸分析）
          · 后端 C：WASM（WASI，文件系统经 effect 显式注入）
```

**性能策略**（函数式语言的关键工程点）：

1. **闭包转换**（Lambda lifting）：顶层绑定变成静态符号；只有逃逸闭包才分配 context
2. **无装箱泛型**：`Vec[Box[a]]` 用类型擦除 +写入屏障，读取处按推断的构造器做**去标签化**（类似 MLton）
3. **effect 不花钱**：所有效应被 CPS 化到顶层 `handle`，内层的 `throw` 只是一条 `raise %label` 指令
4. **尾调用保证**：Core IR 显式区分 tail/non-tail，后端直接 `musttail`
5. **GC**：分代 + 移动式，effect 上下文对象有明确生命周期（线性 handler ⇒ 可栈分配）

---

## 十二、完整示例程序（一个 JSON 解释器）

```lume
module Mini.JSON

enum JValue
  | JNull
  | JBool(v : Bool)
  | JNum(v : Float)
  | JStr(v : String)
  | JArr(items : [JValue])
  | JObj(fields : [(String, JValue)])

struct P = P(input : String, pos : Int)

let parse : String -> Effect[JValue, String]
let parse s = handle
  let p = P(input = s, pos = 0)
  skipWs p
  let v = parseValue p
  expectEnd p
  v
with
  effect Fail[String]:
    op fail(msg : String) = resume (Err (msg ^ " @ " ^ show (posOf self)))

let skipWs p = match at p
  Some c | c == ' ' || c == '\n' -> skipWs (advance p)
  _ -> p

let parseValue p = match at p
  None        -> fail "unexpected end"
  Some '{'    -> parseObj  (advance p) |> finish // | 管道让错误传播显式
  Some '['    -> parseArr  (advance p)
  Some '"'    -> JStr <$> parseStr (advance p)
  Some c | c >= '0' && c <= '9' -> JNum <$> parseNum p
  Some 't'    -> keyword "true"  p . const (JBool true)
  Some 'f'    -> keyword "false" p . const (JBool false)
  Some 'n'    -> keyword "null"  p . const JNull
  Some _      -> fail ("bad char " ^ show (at p))

let eval : JValue -> Env -> Effect[Result, String]      // 一个小栈式求值
let eval v env = match v
  JNum n -> push n env
  JStr s -> push s env
  JBool b -> push b env
  JArr xs -> do
    let e <- env
    traverse_ (\x -> eval x e) xs
    map mkArr e
  _ -> fail "not callable"
```

用法：

```lume
main : Effect[Unit]
main = do
  let cfg <- readFile "prog.json"
  let ast <- parse cfg
  let out <- eval ast emptyEnv
  print (render out)
```

---

## 十三、错误信息设计（LSP 必备）

```
error[E0201]: effect `io` not permitted here ╭─ src/Main.lu:12:3
   │
 12 │   let data = fetch url          // 隐含效应 ! io
   │               ^^^^^^
   ╰────
note: enclosing `pure` function `transform : Tree -> Tree` (line 9)
      does not list `io` in its effect row
help: mark it impure:
        let transform : Effect[Tree] ! { io }
```

三件套：**主因（type/effect/pattern）→ 证据（源码跨度）→ 修复建议（可直接粘贴的代码）**。

---

## 十四、与邻居对比

| 维度 | Lume | Haskell | OCaml | Rust | Nim/TS |
|---|---|---|---|---|---|
| 求值 | 严格（`lazy` 显式） | 惰性 | 严格 | 严格 | 严格 |
| 效应 | 类型级代数效应 | 自由单子 | 可选 | `?` 显式 | 隐式 |
| 空安全 | 无 null | `Maybe` | `option` | `Option` | `?` |
| 穷尽性 | 强制 | 有限（警告级） | 有限 | `match` 强制 | 无 |
| 泛型性能 | 无装箱 | 好 | 好 | 单态 | 差 |
| 推断 | 全推断 + 效应 | 全推断 | 全推断 + 值限制 | 基本无 | 无 |
| 学习成本 | 中 | 高 | 中高 | 高 | 低 |

---

## 十五、路线图

| 阶段 | 时间 | 里程碑 |
|---|---|---|
| **M0 设计定稿** | 3 周 | 本文 + 形式化核心（Lambda + Effect Rows） |
| **M1 前端** | 2 个月 | Lexer/Parser/推断/模式检查 + 解释器（能跑 fib、列表、处理 JSON） |
| **M2 效应** | 2 个月 | handler 语法 + one-shot 运行时 + `io` 标准库 |
| **M3 后端** | 3 个月 | 闭包转换、SSA、LLVM 后端，达到 C 的 1.5× 以内 |
| **M4 生态** | 2 个月 | `lup` 包管理、格式化器、LSP、`@derive` |
| **M5 并发与 FFI** | 2 个月 | 结构化并发、C/WASM FFI |
| **M6 稳定版 1.0** | 1 个月 | 冻结语法、稳定性保证 |

---

## 十六、Lume的一句话总结

> **它是"带类型的 Haskell 精神 + Rust 的显式 + Python 的手感 + 一等代数效应"**：
> `null` 被 `Option` 杀死，异常被类型里的效应行杀死，循环被递归与 `do` 杀死，
> 而**所有这些都是编译期可证明的**；剩下的只有纯粹的数据变换与可组合的计算。

如果你想继续推进，我建议下一步做两件事之一：**（a）写出上述 JSON 解释器的完整可运行代码（含解释器后端）；（b）给出 `Core` 语法的形式化定义与行多态统一算法（Koka 风格的定式规则），让整个设计在纸面上可证明。**
