# [v2:deepseek-flash] 任务1 函数式编程语言 | 条件: baseline | 第 9 次

**Prompt:** 设计一个全新的函数式编程语言

**耗时:** 57.72s | tokens: 37/10821

---

下面给出一个**可落地的全新函数式语言设计草案**，而不是完整 ISO 标准。语言暂名 **Mira（米拉）**。

---

# Mira：以代数效应为一等公民的严格纯函数式语言

## 1. 设计目标

Mira 的目标是：

- **纯函数式核心**：默认不可变、无空指针、无隐式异常。
- **严格求值**：call-by-value，行为可预测，易于编译。
- **代数效应统一 I/O、错误、状态、并发**：不用 monad transformer 堆栈。
- **HM 类型推断 + 行多态**：支持结构记录、结构变体、效应行。
- **可读的 ML/Haskell 风格语法**：`let`、`match`、`fn`、管道 `|>`。
- **可编译**：解释器先行，后端目标 WebAssembly 与 LLVM。
- **工程友好**：模块、显式接口、穷尽性检查、尾调用保证。

非目标：v1 不追求依赖类型、宏系统、隐式类型类、线性类型；这些留给 v2。

---

## 2. 核心语言特性

| 特性 | 设计 |
|---|---|
| 求值策略 | 严格、call-by-value |
| 可变性 | 默认不可变；可变状态通过效应处理器模拟 |
| 类型系统 | Hindley–Milner + 行多态 + 效应行 |
| 数据 | 元组、记录、变体、ADT、列表 |
| 多态 | `forall a. ...`，let 泛化受 value restriction 限制 |
| 效应 | 代数效应与 handler，效应行可多态 |
| 模块 | 命名空间 + 可选签名 |
| 错误处理 | `Option`、`Result`、`Fail` 效应 |
| 并发 | `Async` 效应 + 结构化作用域 |
| 尾调用 | 尾位置调用保证优化 |

---

## 3. 基础语法

### 3.1 定义

```mira
let id = fn x => x

let rec fact =
  fn n =>
    if n == 0 then 1 else n * fact (n - 1)

type Option a = [None | Some a]

type Person = {
  name: Text,
  age: Int
}
```

### 3.2 函数、模式匹配与管道

```mira
let rec map : forall a b. (a -> b) -> List a -> List b =
  fn f xs =>
    match xs with
    | [] -> []
    | x :: rest -> f x :: map f rest

let result =
  [1, 2, 3]
  |> List.map (fn x => x * 2)
  |> List.sum
```

管道语义：

```mira
x |> f   // 等价于 f x
```

### 3.3 记录与行多态

```mira
let name_of : forall r. { name: Text | r } -> Text =
  fn p => p.name

let alice = { name = "Alice", age = 30 }
let n = name_of alice
```

`{ name: Text | r }` 表示“至少有一个 `name: Text` 字段，其他字段由行变量 `r` 表示”。

记录更新：

```mira
let birthday = fn p => { p | age = p.age + 1 }
```

### 3.4 变体

```mira
type Shape =
  [ Circle Float
  | Rectangle Float Float
  | Point ]

let area = fn s =>
  match s with
  | Circle r -> 3.14159 * r * r
  | Rectangle w h -> w * h
  | Point -> 0.0
```

---

## 4. 类型系统

### 4.1 类型语法

```text
T ::= Int | Float | Bool | Char | Text | Unit
    | a
    | (T, ..., T)
    | { l: T, ..., l: T | r }
    | [ C T... | ... ]
    | T -> T ! E
    | forall a. T

E ::= {}                 // 纯
    | { C, ..., C | e }  // 效应行
```

函数类型：

```mira
Int -> Int              // 纯函数
Text -> Unit ! {Console}
```

`Text -> Unit ! {Console}` 表示：给定 `Text`，返回 `Unit`，但求值过程中可能执行 `Console` 效应。

### 4.2 类型规则摘要

- 字面量、lambda、构造器是值。
- `f x`：先推断 `f : A -> B ! E`，再要求 `x : A`，得到 `B ! E`。
- `let` 只对语法值泛化，采用 value restriction，避免效应与多态交互导致不健全。
- 记录和变体使用行统一：重复标签禁止，行变量可扩展。
- 效应行支持弱化：若 `e : T ! E` 且 `E ⊆ E'`，则 `e : T ! E'`。
- `match` 必须穷尽，否则编译错误。

---

## 5. 代数效应

### 5.1 声明效应

```mira
effect Console {
  print : Text -> Unit
}

effect Fail {
  fail : forall a. Text -> a
}
```

### 5.2 调用效应操作

```mira
let greet : Text -> Unit ! {Console} =
  fn name => Console.print ("Hello, " ++ name)
```

### 5.3 Handler

```mira
let run_console : (a ! {Console | e}) -> a ! {IO | e} =
  fn action =>
    handle action with {
      return x -> x

      Console.print(text, k) ->
        let _ = IO.write text in
        k ()
    }
```

语义：

- `handle e with h` 捕获 `e` 中执行到的第一个未处理效应操作。
- `return x` 处理正常返回值。
- 操作分支拿到参数和续延 `k`。
- `k v` 恢复被捕获的续延，并把操作返回值设为 `v`。
- 默认支持多射续延；编译器可对线性 handler 做 one-shot 优化。

Handler 类型规则：

若：

```text
e : A ! {C | E}
return 分支 : A -> B ! E
每个 C.op 分支 : (参数, 续延) -> B ! E
```

则：

```text
handle e with h : B ! E
```

---

## 6. 完整示例

```mira
effect Console {
  print : Text -> Unit
}

type Option a = [None | Some a]

let rec map : forall a b. (a -> b) -> List a -> List b =
  fn f xs =>
    match xs with
    | [] -> []
    | x :: rest -> f x :: map f rest

let name_of : forall r. { name: Text | r } -> Text =
  fn p => p.name

let greet : Text -> Unit ! {Console} =
  fn name => Console.print ("Hello, " ++ name)

let run_console : (a ! {Console | e}) -> a ! {IO | e} =
  fn action =>
    handle action with {
      return x -> x

      Console.print(text, k) ->
        let _ = IO.write text in
        k ()
    }

let main : Unit ! {IO} =
  run_console (greet "Mira")
```

这个程序展示了：

- 纯函数 `map`
- 行多态记录访问
- 代数效应 `Console`
- handler 将 `Console` 解释为 `IO`
- `main` 只暴露 `IO` 效应

---

## 7. 模块与接口

```mira
module List {
  let map = ...
  let filter = ...
}

module Main {
  use List

  let main : Unit ! {IO} = ...
}
```

模块支持：

- 命名空间隔离
- 显式导出列表
- 独立编译
- 模块签名用于接口稳定
- 无隐式全局可变状态

---

## 8. 并发模型

并发通过 `Async` 效应实现：

```mira
effect Async {
  spawn : forall a e. (Unit -> a ! e) -> Task a
  await : forall a. Task a -> a
}
```

结构化并发：

```mira
let scope = fn body =>
  handle body with {
    return x -> x

    Async.spawn(thunk, k) ->
      let task = Scheduler.spawn thunk in
      k task

    Async.await(task, k) ->
      let v = Scheduler.await task in
      k v
  }
```

设计原则：

- 默认结构化并发，子任务不逃逸作用域。
- 调度器本身是 handler，可替换。
- 并发不是语言魔法，而是可解释效应。

---

## 9. 编译与实现方案

推荐实现路线：

1. **Parser**
   - 手写递归下降 + Pratt 表达式解析。
2. **类型检查器**
   - Algorithm W 扩展。
   - 行统一用于记录、变体、效应行。
   - 穷尽性检查与冗余分支检查。
3. **Core IR**
   - ANF 或 CPS。
   - 显式表示效应操作、handler、续延。
4. **解释器**
   - CEK 机器 + handler 栈。
   - 用于语义参考实现和差分测试。
5. **编译器后端**
   - 先编译到 WebAssembly。
   - 通过 CPS 变换实现代数效应。
   - 后续可加 LLVM 后端与 one-shot 续延优化。
6. **运行时**
   - 不可变数据结构。
   - tracing GC。
   - 尾调用优化。
   - `IO`、`Console`、`Task` 等原语。

---

## 10. 与现有语言的差异

Mira 的定位不是“再造一个 Haskell”或“再造一个 OCaml”，而是：

- **严格纯函数核心 + 一等代数效应**
- **记录行、变体行、效应行共用同一套行多态机制**
- **Handler 即能力解释器**：I/O、错误、并发、状态都可被库解释
- **默认无 ambient IO**
- **强调可编译性与可预测性能**
- **v1 保持小而完整，避免类型类、宏、依赖类型同时引入**

---

## 11. 总结

Mira 是一个以 **纯函数、严格求值、HM 类型推断、行多态、代数效应** 为核心的函数式语言。它用统一的“行”机制描述记录、变体和效应，用 handler 统一解释 I/O、错误、状态与并发。语法接近 ML/F#，但语义核心更接近“可编译的代数效应语言”。

最小可行版本可以只实现：

```text
let / fn / if / match
Int / Bool / Text / List / Option
记录与变体
algebraic effects + handler
HM + row polymorphism
```

之后逐步加入模块签名、`Async`、优化编译器和标准库。
