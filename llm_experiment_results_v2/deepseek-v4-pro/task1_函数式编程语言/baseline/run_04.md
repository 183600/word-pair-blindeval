# [v2:deepseek-v4-pro] 任务1 函数式编程语言 | 条件: baseline | 第 4 次

**Prompt:** 设计一个全新的函数式编程语言

**耗时:** 139.21s | tokens: 90/9935

---

下面是我设计的一个全新函数式编程语言概念，暂名 **Aster**。

## 设计理念

Aster 的核心目标不是简单地“再做一个 Haskell 或 OCaml”，而是把三类现代函数式语言里常被割裂的能力统一起来：

- **代数效应**：异常、状态、IO、并发、非确定性都由 effect 描述，而不是靠 monad 堆叠。
- **行多态**：同一套 row polymorphism 同时用于记录、变体和副作用。
- **结构化并发**：所有并发任务都是可组合、可取消、可追踪的 fiber。
- **默认纯函数、不可变数据**：副作用必须在类型中可见。

Aster 的关键字尽量少，语法偏向表达式和缩进，类型系统足够强但并不把用户淹没在类型标注里。

---

## 1. 类型系统

Aster 是强静态类型语言，支持全局类型推断。类型参数使用小写字母，默认全称量化。

```text
id : a -> a
id x = x
```

### 代数数据类型

```text
type Option a =
  | None
  | Some a

type Tree a =
  | Leaf
  | Node (Tree a) a (Tree a)
```

模式匹配：

```text
fn depth : Tree a -> Int
fn depth t =
  match t with
  | Leaf -> 0
  | Node l _ r -> 1 + max (depth l) (depth r)
```

### 记录与行多态

记录是结构化的，可以自由扩展：

```text
let user = { name = "Ada", age = 36 }
let user2 = { user | age = 37 }

user.name          -- "Ada"
```

类型为 `{ name : String, age : Int }`。

行多态允许写成：

```text
fn getName : { name : String | r } -> String
fn getName r = r.name
```

这样任何包含 `name` 字段的记录都可以传入。

### 开放变体

变体同样支持行多态：

```text
type Event = [ Click { x : Int, y : Int }, Key String ]

fn clickSum : [ Click { x : Int, y : Int } | r ] -> Int
fn clickSum ev =
  match ev with
  | Click { x, y } -> x + y
  | other -> 0
```

`other` 分支保留了可扩展性，这意味着某个 API 可以先定义 `Click`，后续模块继续增加 `Scroll`、`Drag`，旧代码不需要修改。

### 轻量依赖类型

Aster 支持有限的类型级自然数，用来增强容器安全性，但不引入完整依赖类型：

```text
type Vec : Nat -> Type -> Type
type Vec n a =
  | VNil  : Vec 0 a
  | VCons : a -> Vec n a -> Vec (n + 1) a

fn head : Vec (n + 1) a -> a
fn head (VCons x _) = x
```

调用 `head VNil` 会在编译期被拒绝。

---

## 2. 代数效应系统

这是 Aster 最重要的部分。

副作用不是函数类型的额外参数，也不是 monad，而是显式的 effect。

### 声明 effect

```text
effect Log(msg : String) : Unit
effect Fetch(url : String) : String
```

### 执行 effect

```text
fn loadUser : Int -> User / [Fetch, Log]
fn loadUser id =
  let url = "https://api/users/" ++ intToString id

  perform Log("fetching " ++ url)
  let json = perform Fetch(url)

  parseUser json
```

函数类型中的 `[Fetch, Log]` 表示该函数可能执行这两种 effect。

纯函数可以省略 effect 行，例如：

```text
fn add : Int -> Int -> Int
fn add x y = x + y
```

实际上它是：

```text
fn add : Int -> Int -> Int / []
fn add x y = x + y
```

### 处理 effect

使用 `handle ... with` 可以消除某个 effect。

```text
fn main : User
fn main =
  handle loadUser 1 with {
    Log msg -> {
      print(msg)
      resume ()
    }
    Fetch url -> {
      resume mockResponse
    }
  }
```

`resume` 表示“继续原计算”。对于 `Log`，原计算期望返回 `Unit`，所以是 `resume ()`；对于 `Fetch`，原计算期望返回 `String`，所以是 `resume mockResponse`。

处理后，`[Fetch, Log]` 被移除，得到纯 `User`。

这比 monad transformer 更容易组合，也比异常系统更可预测。

---

## 3. 管道与组合

Aster 鼓励数据流风格的代码。`|>` 将左侧表达式作为右侧函数的最后一个参数。

```text
fn square x = x * x

fn sumSquares xs =
  xs
  |> map square
  |> fold (+) 0
```

函数组合：

```text
let stringToInt = trim >> parseInt
```

---

## 4. 接口与实现

Aster 使用接口提供 ad-hoc 多态，类似 Rust trait，但更轻。

```text
interface Show a {
  show : a -> String
}

type User = { id : Int, name : String }

impl Show User {
  show u = u.name
}

fn display : Show a => a -> Unit / [IO]
fn display x =
  print(show x)
```

约束 `Show a =>` 放在函数类型中，表示 `a` 必须实现 `Show`。

---

## 5. 结构化并发

Aster 不提供裸线程，而是提供 fiber。

```text
effect Sleep(ms : Int) : Unit

fn task(name : String) : String / [Sleep] =
  perform Sleep(100)
  name

fn main : [String] / [Sleep] =
  let f1 = spawn { task "a" }
  let f2 = spawn { task "b" }
  par [f1, f2]
```

说明：

- `spawn { ... }` 创建一个 fiber，表达式不会立即执行。
- `par` 等待所有 fiber 完成，并返回结果列表。
- `race` 可以竞速执行多个 fiber，并自动取消较慢的 fiber。
- 作用域结束时，未完成的 fiber 会被自动取消，避免泄漏。

由于 fiber 也是通过 effect 描述，调度器可以被替换、测试或嵌入到不同运行时中。

---

## 6. 模块系统

模块是一个一等公民，但不追求 OCaml 那样复杂的 functor 系统。

```text
module Math exposing (pi, factorial)

pi : Float
pi = 3.141592653589793

factorial : Int -> Int
factorial n =
  if n <= 1 then 1 else n * factorial (n - 1)
```

导入：

```text
import Math as M

fn circleArea r = M.pi * r * r
```

---

## 7. 完整综合示例

下面是一个更完整的程序，展示了记录、变体、代数效应、管道和并发。

```text
effect Log(msg : String) : Unit
effect Fetch(url : String) : String
effect Delay(ms : Int) : Unit

type User = { id : Int, name : String, age : Int }

type LoadResult = [ Ok User | NotFound | NetworkError String ]

fn parseUser : String -> LoadResult
fn parseUser json =
  if json == "" then NotFound else Ok { id = 1, name = "Ada", age = 36 }

fn fetchUser : Int -> LoadResult / [Fetch, Log]
fn fetchUser id =
  let url = "https://api/users/" ++ intToString id

  perform Log("fetch " ++ url)
  perform Delay(50)
  let json = perform Fetch(url)

  parseUser json

fn main : Unit
fn main =
  let ids = [1, 2, 3]

  let fibers =
    ids
    |> map (fun id -> spawn { fetchUser id })

  let results = par fibers

  handle results with {
    Log msg -> { print(msg); resume () }
    Fetch url -> { resume """{"id":1,"name":"Ada","age":36}""" }
    Delay ms -> { resume () }
  }
  |> map printResult
  |> ignore
```

其中：

- `map (fun id -> spawn { fetchUser id })` 创建多个并发请求。
- `par fibers` 等待全部完成。
- `handle ... with` 统一处理所有 effect。
- 最后用管道处理结果。

---

## 8. 与现有语言的区别

| 特性 | Aster | Haskell | OCaml | Elm |
|---|---|---|---|---|
| 副作用建模 | 代数效应 | Monad | 直接副作用 | Managed effects |
| 记录扩展 | 行多态 | 较差 | 对象/记录 | 行多态 |
| 变体扩展 | 开放变体 | 封闭 ADT | 多态变体 | 封闭 ADT |
| 并发 | 结构化 fiber | 复杂 | 库/线程 | 任务 |
| 默认不可变 | 是 | 是 | 否 | 是 |
| 类型推断 | 全局 | 全局 | 局部 | 全局 |

Aster 的独特之处在于：**一套行多态同时服务记录、变体和 effect**，并用代数效应统一了状态、异常、IO 和并发。

如果你愿意，下一步我可以继续展开某一部部分，例如：

- 完整类型推断规则；
- 代数效应处理器语义；
- 标准库设计；
- 编译器实现路线图；
- FFI 与运行时模型。
