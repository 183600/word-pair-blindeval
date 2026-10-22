# [v2:deepseek-flash] 任务1 函数式编程语言 | 条件: baseline | 第 4 次

**Prompt:** 设计一个全新的函数式编程语言

**耗时:** 44.07s | tokens: 37/8306

---

下面给出一门原创概念语言 **Vela（维拉）** 的完整设计草案。它是一门**纯函数式、强类型、严格求值、效应显式、面向数据流水线**的通用编程语言。工作名 Vela 取自“帆”，强调“数据流”和“可组合变换”。

---

## 1. 设计目标

Vela 的核心口号：

> **一切计算都是带类型的数据变换；一切副作用都是可替换的效应。**

设计原则：

1. **默认纯函数**：普通函数不能产生副作用。
2. **副作用显式化**：IO、网络、随机数、异常、并发等通过效应行类型标注。
3. **严格求值**：默认 call-by-value，性能可预测；惰性用显式 `Lazy`/`Stream`。
4. **数据优先**：行多态记录、变体、模式匹配、管道操作是语言核心。
5. **类型推断友好**：Hindley–Milner + 双向检查 + 行多态 + 效应行。
6. **不用 monad 也能写效果代码**：代数效应和 handler 是一等公民。
7. **并发结构化**：`async` 作用域自动取消、等待、传播错误。

---

## 2. 一页速览

| 项目 | 设计 |
|---|---|
| 范式 | 纯函数式 + 代数效应 |
| 求值 | 严格，显式惰性 |
| 类型系统 | HM + 双向检查 + 行多态 + 效应行 |
| 数据类型 | 记录、变体、元组、列表、流 |
| 模式匹配 | 支持穷尽性检查 |
| 副作用 | 效应行 `! {io, fs}` |
| 并发 | 结构化 `async/await` |
| 模块 | ML 风格模块 + 显式导出 |
| 后端 | WASM、LLVM |
| 工具链 | `velac`、`vela`、`velafmt`、`vela-lsp` |

---

## 3. 基础语法示例

### Hello World

```vela
module Main

import Std.IO

fn main() -> Unit ! {io} =
  Console.println("Hello, Vela!")
```

`main` 的 `! {io}` 表示它允许使用 IO 效应。普通函数没有 `!` 则是纯函数。

---

### 函数与管道

```vela
fn double(x: Int) -> Int =
  x * 2

fn main() -> Unit ! {io} =
  [1, 2, 3, 4]
  |> List.map double
  |> List.filter (fn x -> x > 4)
  |> List.each (fn x -> Console.println (show x))
```

`|>` 是管道：

```vela
x |> f  ==  f x
```

---

### 记录与行多态

```vela
type User = {
  id: Int,
  name: String,
  tags: List String
}

fn greet(user: { name: String | r }) -> String =
  "Hello, " + user.name + "!"

fn main() -> Unit ! {io} =
  let u = { id = 1, name = "Ada", tags = ["math", "logic"] }
  Console.println(greet u)
```

类型 `{ name: String | r }` 表示“至少含有 `name: String` 字段，其他字段由行变量 `r` 表示”。这样 `greet` 可以接收任何带 `name` 字段的记录。

---

### 变体与模式匹配

```vela
type Expr =
  | Lit Int
  | Add Expr Expr
  | Mul Expr Expr

fn eval(e: Expr) -> Int =
  match e with
  | Lit n    -> n
  | Add a b  -> eval a + eval b
  | Mul a b  -> eval a * eval b
```

模式匹配要求穷尽所有变体，否则编译错误。

---

## 4. 效应系统

### 4.1 效应声明

```vela
effect Logger {
  log: String -> Unit
}
```

### 4.2 使用效应

```vela
fn compute() -> Int ! {Logger} =
  Logger.log("computing")
  6 * 7
```

`compute` 的类型是：

```vela
compute : Unit -> Int ! {Logger}
```

它只能执行纯计算和 `Logger` 效应。

### 4.3 处理效应

```vela
fn main() -> Unit ! {io} =
  let value =
    handle compute() with {
      Logger.log(msg, resume) ->
        Console.println("[log] " + msg)
        resume ()
    }
  Console.println("result = " + show value)
```

`handle` 捕获 `Logger` 效应，并提供解释器。`resume` 是续延，调用它继续执行被挂起的计算。

效应可以组合：

```vela
fn program() -> Int ! {io, fs, Logger} =
  ...
```

handler 可以消去某一种效应：

```vela
handle program() with Logger { ... }
```

结果类型中的 `Logger` 被消去，只留下 `{io, fs}`。

---

## 5. 类型系统

Vela 的类型可以概括为：

```text
τ ::= α
    | Int | Bool | String
    | List τ
    | τ -> τ ! ε
    | { l: τ, ... | ρ }
    | [ l: τ, ... | ρ ]
    | μ α. τ
    | ∀ α:κ. τ

ε ::= ∅
    | { E, ... | ρ }

κ ::= Type | Row | Effect
```

其中：

- `ρ` 是行变量，用于记录和变体。
- `ε` 是效应行，表示允许的副作用集合。
- `μ α. τ` 支持递归类型。
- `∀` 支持显式多态。

类型推断采用：

1. 双向类型检查：`infer` 与 `check`。
2. 行统一：处理记录、变体、效应行。
3. `let` 泛化：采用 effect-aware value restriction，只泛化纯值或显式标注为纯的表达式。
4. 所有顶层函数类型必须可推断或显式标注。
5. 支持穷尽性检查和冗余分支警告。

---

## 6. 求值语义

Vela 默认采用 call-by-value、从左到右求值。

纯核心演算可表示为：

```text
e ::= x
    | c
    | λx. e
    | e e
    | let x = e in e
    | { l = e, ... }
    | e.l
    | match e with p -> e
    | perform E e
    | handle e with H
```

求值规则要点：

- 函数参数先求值。
- 记录字段按声明顺序求值。
- `match` 按模式顺序匹配。
- `perform E v` 查找最近的处理器。
- `handle e with H` 安装效应处理器。
- 纯表达式满足引用透明性。
- 惰性通过 `Lazy a` 和 `Stream a` 显式表达。

---

## 7. 并发模型

Vela 使用结构化并发：

```vela
fn fetchAll(urls: List String) -> List Response ! {network, async} =
  urls
  |> List.map (fn url -> async Http.get url)
  |> List.map await
```

`async` 创建的任务绑定到当前作用域。作用域退出时：

- 自动等待未完成任务；
- 若有异常或取消，自动取消兄弟任务；
- 不允许任务泄漏到作用域外。

错误处理使用 `Result`：

```vela
type Result a e =
  | Ok a
  | Err e
```

也可以把异常建模为效应：

```vela
effect Throw e {
  throw: e -> Never
}
```

然后通过 handler 转换为 `Result`。

---

## 8. 模块系统

```vela
module Data.User exposing (User, greet)

import Std.String as S

type User = {
  id: Int,
  name: String
}

fn greet(user: User) -> String =
  "Hello, " + user.name
```

模块默认私有，只有 `exposing` 中列出的名字对外公开。模块接口可以显式声明：

```vela
interface Show a {
  show: a -> String
}
```

接口通过字典传递实现，类似 type class，但不引入隐式全局实例搜索，避免“魔法”。

---

## 9. 标准库与工具链

建议标准库分层：

- `Std.Core`：`Option`、`Result`、`List`、`Map`、`Set`、`String`
- `Std.IO`：控制台、文件、进程
- `Std.Net`：HTTP、TCP
- `Std.Async`：结构化并发
- `Std.Test`：属性测试、快照测试
- `Std.Data`：JSON、CSV、时间、正则

工具链：

- `velac`：编译器
- `vela`：包管理器与构建工具
- `velafmt`：格式化器
- `vela-lsp`：语言服务器
- `vela test`：测试运行器
- REPL：`vela repl`

编译流程：

```text
源码
  -> 词法/语法分析
  -> 名称解析
  -> 类型检查 + 效应检查
  -> 去糖为核心演算
  -> ANF/CPS 转换
  -> 优化
  -> WASM / LLVM 后端
```

效应 handler 可以编译为 CPS、evidence passing 或 free monad 风格运行时。

---

## 10. 与现有语言的区别

- 相比 Haskell：默认严格求值，不要求用 monad 组织副作用，效应行直接写在类型里。
- 相比 OCaml：默认纯函数，副作用必须显式声明；记录/变体支持行多态。
- 相比 Elm：不止面向前端，目标是通用语言；支持代数效应和结构化并发。
- 相比 Koka：语法更面向数据管道，记录/变体与模式匹配更接近应用开发者习惯。
- 相比 Rust：无所有权系统，但通过不可变默认值、区域分析和 GC 获得可预测性能。

---

## 11. 总结

**Vela** 的核心设计可以概括为：

> **纯函数 + 行多态数据 + 效应行 + handler + 管道式组合。**

它试图在可预测性、表达力和工程可用性之间取得平衡：普通代码保持纯函数式，副作用通过效应类型显式表达，数据转换通过记录、变体、模式匹配和管道自然组合。

如果你愿意，下一步可以继续设计 Vela 的**形式语法、类型规则、最小解释器或用 Rust 实现的编译器原型**。
