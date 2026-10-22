# [v2:deepseek-flash] 任务1 函数式编程语言 | 条件: baseline | 第 1 次

**Prompt:** 设计一个全新的函数式编程语言

**耗时:** 27.64s | tokens: 37/5284

---

下面给出一份可落地的函数式编程语言设计草案。语言名为 **Aster（星芒）**：默认纯函数、强类型、显式效应、结构化并发、布局语法。

---

# Aster（星芒）语言设计草案

## 1. 定位

Aster 是一门：

- **默认纯函数式**的语言；
- **严格求值**、默认不可变；
- 使用 **代数数据类型 + 模式匹配**；
- 使用 **类型与效应行** 显式描述副作用；
- 内建 **结构化并发**；
- 采用 **布局语法 + 管道表达式**，强调可读性；
- 小核心、大标准库，适合脚本、服务端和 WASM。

非目标：类继承、隐式全局状态、隐藏异常控制流、可空引用。

---

## 2. 核心设计原则

1. **纯函数是默认值**  
   函数不产生副作用，除非类型里写明效应。

2. **副作用是类型的一部分**  
   例如 `fn main() -> Unit with Console` 表示会使用控制台效应。

3. **值语义 + 结构共享**  
   值不可变，但列表、映射等使用持久化数据结构共享内存。

4. **表达式导向**  
   `if`、`match`、块、`handle` 都是表达式。

5. **显式优于隐式**  
   错误是 `Result` 或 `Error` 效应；并发必须通过 `Async` 效应与作用域；可变状态必须通过 `State`/`Ref` 效应。

---

## 3. 基本语法

### 3.1 模块与函数

```aster
module Main

use std.io

effect Console
  print: String -> Unit
  read_line: Unit -> String

fn greet(name: String) -> Unit with Console =
  Console.print("Hello, " <> name)

fn main() -> Unit with Console =
  greet("Aster")
```

函数形式：

```aster
fn name[a, b](x: a, y: b) -> Ret with Effects =
  expr
```

- `[a, b]` 是显式类型参数；
- `with Effects` 是效应行；
- 无副作用时省略 `with`。

### 3.2 数据与模式匹配

```aster
data List[a] = Nil | Cons(a, List[a])

data Result[e, a] = Err(e) | Ok(a)

fn map[a, b](f: a -> b, xs: List[a]) -> List[b] =
  match xs
    Nil -> Nil
    Cons(x, rest) -> Cons(f(x), map(f, rest))
```

模式匹配要求完备性检查。

### 3.3 记录与行多态

```aster
type User = { id: Int, name: String, email: String }

fn display_name[u](user: { name: String, ..u }) -> String =
  user.name
```

`..u` 表示“还可能有其他字段”，实现记录行多态。

### 3.4 管道

```aster
fn inc(x: Int) -> Int = x + 1
fn double(x: Int) -> Int = x * 2

fn compute(x: Int) -> Int =
  x |> inc |> double
```

`x |> f` 等价于 `f(x)`。

---

## 4. 类型系统

Aster 的类型系统包括：

- Hindley–Milner 风格类型推断；
- 泛型；
- 代数数据类型；
- 记录与行多态；
- 效应行；
- 接口/字典式类型类；
- 完备性检查与尾调用优化。

函数类型写作：

```text
A -> B with E
```

其中 `E` 是效应行。纯函数：

```text
A -> B
```

等价于：

```text
A -> B with {}
```

效应行可以组合：

```aster
fn run() -> Unit with {Console, Error[String]} =
  ...
```

也可以用行变量：

```aster
fn log_then[a](x: a) -> a with {Console, ..e} =
  Console.print(show(x))
  x
```

---

## 5. 代数效应

Aster 用代数效应统一描述 IO、错误、状态、并发等副作用。

### 声明效应

```aster
effect Error[e]
  throw: e -> Never

effect State[s]
  get: Unit -> s
  put: s -> Unit
```

### 使用效应

```aster
fn safe_div(a: Int, b: Int) -> Result[String, Int] =
  handle
    if b == 0 then Error.throw("division by zero") else a / b
  with
    Error.throw(msg, _resume) -> Err(msg)
```

`handle expr with ...` 处理效应。处理器可以恢复续体，也可以丢弃续体。

### 内置常用效应

```text
Console
Fs
Net
Random
Time
Error[e]
State[s]
Async
```

效应处理具有能力语义：获得处理器，才获得相应能力。

---

## 6. 并发模型

并发通过 `Async` 效应和结构化作用域实现：

```aster
fn fetch_all(urls: List[String]) -> List[Response] with Async =
  scope
    let tasks = urls |> map(fn url -> spawn fetch(url))
    tasks |> map(await)
```

原则：

- `spawn` 创建的任务必须属于当前 `scope`；
- 离开作用域前自动等待或取消子任务；
- 默认无共享可变状态；
- 需要共享状态时显式使用 `State` 或 `Ref` 效应；
- 取消是协作式的，并沿结构化作用域传播。

---

## 7. 模块、可见性与工程化

```aster
module MyApp.Users

pub type User = { id: Int, name: String }

pub fn by_id(id: Int) -> Option[User] with Fs =
  ...
```

- `pub` 控制导出；
- `use` 导入模块；
- 文件和模块一一对应；
- 包管理器命令为 `aster`；
- 标准工具：格式化器 `aster fmt`、REPL `aster repl`、测试 `aster test`、LSP `aster lsp`。

---

## 8. 求值与运行时

- 严格求值，保证可预测性能；
- 惰性值通过显式 `Lazy[a]` 提供；
- 尾递归优化；
- 不可变值 + 持久化数据结构；
- 运行时使用 tracing GC；
- 中间表示基于 ANF/CPS，便于实现效应处理器；
- REPL 使用字节码 VM；
- 生产后端可生成 LLVM IR 或 WASM。

---

## 9. 示例：完整小程序

```aster
module Todo

use std.io

type Todo = {
  id: Int,
  title: String,
  done: Bool
}

effect State[s]
  get: Unit -> s
  put: s -> Unit

fn add_todo(title: String) -> Unit with State[List[Todo]] =
  let todos = State.get(())
  let next_id = length(todos)
  let todo = { id: next_id, title: title, done: false }
  State.put(Cons(todo, todos))

fn main() -> Unit with {Console, State[List[Todo]]} =
  add_todo("Learn Aster")
  let todos = State.get(())
  Console.print(show(todos))
```

---

## 10. 实现路线

1. **M0**：词法、解析、AST、REPL 解释器；
2. **M1**：HM 类型推断、ADT、模式匹配；
3. **M2**：记录行多态、接口/字典；
4. **M3**：效应行、`handle`、内置 `Console/Error/State`；
5. **M4**：结构化并发与 `Async`；
6. **M5**：字节码 VM、WASM/LLVM 后端、包管理器与 LSP。

---

## 11. 设计取舍总结

Aster 的关键选择是：

- **严格求值**，而不是默认惰性；
- **显式效应**，而不是任意副作用；
- **不可变值语义**，而不是共享可变对象；
- **结构化并发**，而不是裸线程；
- **类型推断 + 行多态**，兼顾安全与简洁；
- **小核心语言 + 大标准库**，降低规范复杂度。

一句话概括：**Aster 是一门“纯函数为核心、效应显式化、并发结构化、类型可推断”的现代函数式语言。**
