# [v2:deepseek-flash] 任务1 函数式编程语言 | 条件: baseline | 第 5 次

**Prompt:** 设计一个全新的函数式编程语言

**耗时:** 43.33s | tokens: 37/8587

---

可以。下面给出一个从零设计的函数式编程语言草案，工作名 **Mora**。它的核心选择是：

> **纯函数默认 + 显式效应行 + 结构化并发 + HM 类型推断 + 可读语法 + 可预测性能。**

Mora 不是把现有语言换皮，而是围绕“函数式核心、副作用可见、并发可控”来设计。

---

## 1. 设计原则

1. **纯函数默认**  
   普通函数没有隐藏副作用；所有副作用都写进类型。

2. **表达式导向**  
   `if`、`match`、块、循环抽象都是表达式，都有值。

3. **不可变优先**  
   值是默认不可变的；状态变化通过新值或显式 `State` 效应表达。

4. **无 `null`**  
   用 `Option[a]` 表示可能缺失，用 `Result[e, a]` 或 `Fail[e]` 效应表示错误。

5. **并发结构化**  
   任务只能存在于 `scope` 中；`scope` 结束时自动等待或取消，不允许默认“游离任务”。

6. **语法服务可读性**  
   使用缩进结构、管道 `|>`、模式匹配、类型后置。

---

## 2. 基础语法

函数是一等值，参数分组，支持部分应用：

```mora
fn add(x: Int)(y: Int) -> Int =
  x + y

let inc = add(1)
inc(2)  // 3
```

顶层 `fn` 默认递归；局部递归用 `let rec`。

管道：

```mora
xs
  |> List.map(double)
  |> List.filter(is_even)
  |> List.fold(0)(add)
```

注释使用 `//` 和 `/* ... */`。

---

## 3. 数据与模式匹配

代数数据类型：

```mora
data Tree[a] =
  | Leaf
  | Node(Tree[a], a, Tree[a])

data Option[a] =
  | None
  | Some(a)
```

记录是结构化的，并支持行多态：

```mora
type Person = {
  name: String,
  age: Int
}

fn greet(p: { name: String | r }) -> String =
  "Hello, {p.name}"
```

模式匹配必须穷尽：

```mora
fn insert[a: Ord](x: a)(t: Tree[a]) -> Tree[a] =
  match t
    | Leaf -> Node(Leaf, x, Leaf)
    | Node(l, y, r) ->
        if x < y then Node(insert(x)(l), y, r)
        else if x > y then Node(l, y, insert(x)(r))
        else t
```

---

## 4. 类型系统

Mora 使用 **Hindley–Milner 类型推断**，并加入：

- 参数多态：`fn identity[a](x: a) -> a`
- 代数数据类型
- 结构化记录与行多态
- 接口 / 类型类
- 穷尽性检查
- 无隐式数值转换
- 模块边界鼓励显式类型标注

接口示例：

```mora
interface Eq[a] {
  eq: (a, a) -> Bool
}

impl Eq[Int] {
  eq(x, y) = x == y
}
```

---

## 5. 效应系统：Mora 的标志性设计

Mora 中所有副作用都进入函数类型末尾的 **效应行**：

```mora
A -> B          // 纯函数
A -> B ! {IO}   // 有 IO 效应
A -> B ! {IO, State[Int], Fail[Error]}
```

`{}` 表示纯。效应行支持行多态，因此高阶函数可以写成效应多态函数。

内置效应包括：

```mora
IO
Fail[E]
State[S]
Async
Random
Clock
```

函数可声明效应：

```mora
fn tick() -> Int ! {State[Int]} =
  let n = get()
  put(n + 1)
  n
```

效应通过 handler 解释：

```mora
fn run_state[s, a](init: s)(action: Unit -> a ! {State[s]}) -> a ! {}
  handle action() with State(init) {
    get()   => resume(state)
    put(s') => resume(()) with state = s'
  }
```

处理器默认是 **one-shot continuation**，便于高效编译；需要多次重入时显式标注 `multi`。

---

## 6. 错误处理

Mora 提供两种互补机制：

1. 纯数据错误：`Result[E, A]`
2. 可传播效应：`Fail[E]`，配合 `?` 运算符

```mora
fn read_config(path: String) -> Config ! {IO, Fail[Error]} =
  let text = read_file(path)?
  parse_config(text)?
```

不可恢复错误使用 `panic`，但类型系统会把它标成 `Panic` 效应，调用方必须显式允许或处理。

---

## 7. 结构化并发

并发是效应，不是魔法：

```mora
fn fetch_all(urls: List[String]) -> List[Response] ! {IO, Async} =
  scope
    let tasks = urls |> List.map(fn u => spawn fetch(u))
    tasks |> List.map(await)
```

规则：

- `spawn` 只能在 `scope` 内使用
- `scope` 结束前等待所有子任务
- 任一子任务失败可触发同级取消
- 默认禁止直接共享可变状态
- 线程间通信推荐不可变消息或 `Chan[a]`

---

## 8. 模块与工具链

模块：

```mora
module Geometry exposing (Point, distance)

import Std.Math
```

工具链：

```bash
mora init
mora check
mora run
mora test
mora fmt
mora build --target wasm32
```

后端目标：

- WebAssembly
- 原生代码：LLVM 或 Cranelift
- 解释器 / REPL

内存策略：

- 默认不可变持久数据结构
- 分代 GC
- 编译器做逃逸分析、尾调用优化、流融合
- 后续可加入 `unique` / 线性类型作为原地更新优化

---

## 9. 示例：Hello World

```mora
module Main

import Std.IO

fn main() -> Unit ! {IO} =
  let name = read_line()
  println("Hello, {name}!")
```

这里 `main` 明确暴露 `IO` 效应；没有隐式副作用。

---

## 10. 一个完整小程序

```mora
module Main

import Std.IO
import Std.List

data Tree[a] =
  | Leaf
  | Node(Tree[a], a, Tree[a])

fn insert[a: Ord](x: a)(t: Tree[a]) -> Tree[a] =
  match t
    | Leaf -> Node(Leaf, x, Leaf)
    | Node(l, y, r) ->
        if x < y then Node(insert(x)(l), y, r)
        else if x > y then Node(l, y, insert(x)(r))
        else t

fn to_list[a](t: Tree[a]) -> List[a] =
  match t
    | Leaf -> Nil
    | Node(l, x, r) ->
        to_list(l) ++ Cons(x, to_list(r))

fn main() -> Unit ! {IO} =
  let tree =
    [3, 1, 4, 1, 5]
      |> List.fold(Leaf)(fn acc, x => insert(x)(acc))

  tree |> to_list |> List.map(show) |> List.join(", ") |> println
```

---

## 11. MVP 范围建议

第一版只实现：

- 函数、`let`、模式匹配
- ADT、记录、HM 推断
- `Option` / `Result` / `List`
- `IO`、`Fail`、`State` 三种效应
- one-shot handler
- 单线程结构化并发
- Wasm 后端
- formatter、REPL、包管理雏形

后续再加入：

- 效应多态优化
- multi-shot handler
- 线性 / 唯一类型
- 分布式 `Async`
- 形式化语义与类型规则

---

总结来说，**Mora** 的语言身份是：

> 一个“副作用必须出现在类型里”的纯函数式语言；用效应行和 handler 统一错误、状态与并发；用结构化并发保证任务生命周期安全；用 HM 推断保持语法轻量。

如果你愿意，下一步我可以继续给出 **Mora 的 EBNF 语法规范**、**类型规则与效应行推断规则**，或者 **编译器前端架构设计**。
