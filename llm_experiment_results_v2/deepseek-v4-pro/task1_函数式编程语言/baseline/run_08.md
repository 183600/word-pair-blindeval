# [v2:deepseek-v4-pro] 任务1 函数式编程语言 | 条件: baseline | 第 8 次

**Prompt:** 设计一个全新的函数式编程语言

**耗时:** 132.31s | tokens: 90/10982

---

# 设计一种全新的函数式编程语言：Rune

Rune 是一个暂定名。它是一门**纯函数式、强静态类型、以代数效应为核心副作用模型**的语言，目标是在保持表达力的同时，提供比传统 Monad 更直观的副作用组合方式，并兼顾现代工程体验。

---

## 1. 设计哲学

Rune 的核心设计原则：

1. **纯函数为默认**  
   函数默认不能执行副作用。任何副作用都必须显式声明在函数签名中。

2. **副作用是一等公民**  
   异常、状态、日志、非确定计算、并发等，都通过统一的**代数效应（algebraic effects）**机制表达，而不是依赖 Monad Transformer。

3. **严格求值，惰性可选**  
   默认严格求值，降低隐式性能成本；需要惰性时显式使用 `Stream` 或 `Lazy`。

4. **结构类型与行多态**  
   记录和变体默认采用行多态，减少样板代码，同时保证类型安全。

5. **类型推断友好**  
   支持全局类型推断，包括效果推断。复杂公开 API 可以标注类型，局部代码可以省略。

6. **可组合、可测试**  
   效果处理器可以自由替换，便于单元测试和模拟外部依赖。

---

## 2. 核心语法

### 2.1 值与表达式

```rune
let x = 1
let name = "Rune"
let values = [1, 2, 3]       // List<Int>
let tuple = (1, "a")
```

所有结构默认不可变。

---

### 2.2 函数

函数默认柯里化：

```rune
fn add(a: Int, b: Int) -> Int {
  a + b
}

let inc = add(1)             // Int -> Int
inc(41)                      // 42
```

支持管道操作符：

```rune
[1, 2, 3, 4]
  |> List.map(\x -> x * 2)
  |> List.filter(\x -> x > 4)
  |> List.sum
// 结果：14
```

---

### 2.3 代数数据类型与模式匹配

```rune
type Option<a> =
  | None
  | Some(a)

type Tree<a> =
  | Leaf
  | Node(Tree<a>, a, Tree<a>)

fn sumTree(tree: Tree<Int>) -> Int {
  match tree {
    Leaf => 0
    Node(left, value, right) =>
      sumTree(left) + value + sumTree(right)
  }
}
```

模式匹配支持嵌套、守卫条件、`as` 模式等。

---

### 2.4 记录与行多态

```rune
let alice = { name: "Alice", age: 30 }

fn nameOf(p: { name: String | r }) -> String {
  p.name
}

nameOf(alice)                              // "Alice"
nameOf({ name: "Bob", admin: true })       // "Bob"
```

记录更新返回新值：

```rune
let olderAlice = { ...alice, age: 31 }
```

行多态意味着：函数只要求“至少有某个字段”，而不要求具体类型。这让组合和扩展非常灵活。

---

## 3. 类型类

Rune 使用类型类（trait）实现接口抽象：

```rune
trait Show<a> {
  fn show(value: a) -> String
}

impl Show<Int> {
  fn show(value: Int) -> String { intToString(value) }
}

impl Show<Bool> {
  fn show(value: Bool) -> String {
    if value then "true" else "false"
  }
}

fn printEach<a>(xs: List<a>) -> Unit
  effects {IO}
  where Show<a>
{
  xs |> List.iter(\x -> println(show(x)))
}
```

类型类支持默认实现和实现组合，但不引入继承链。

---

## 4. 效果系统与代数效应

这是 Rune 最重要的特性。副作用不通过 `IO` 单子隔离，而是通过效果声明、触发和处理来建模。

### 4.1 声明效果

```rune
effect Logger {
  log(msg: String) -> Unit
}

effect State<s> {
  get() -> s
  put(value: s) -> Unit
}
```

### 4.2 触发效果

```rune
fn bankAccount() -> Int
  effects {Logger, State<Int>}
{
  perform Logger.log("started")
  let current = perform State.get()
  perform State.put(current + 100)
  perform Logger.log("new balance")
  current
}
```

`perform` 会暂停当前计算，把操作交给最近的处理器。

### 4.3 处理效果

```rune
fn main() -> Unit effects {IO} {
  let result =
    handle {
      bankAccount()
    } with {
      Logger.log(msg) => {
        println("LOG: " + msg)
        resume(())
      }
      State.get() => {
        resume(10)
      }
      State.put(v) => {
        resume(())
      }
    }

  println("result: " + intToString(result))
}
```

处理器可以调用 `resume` 恢复原计算。也可以选择不调用 `resume`，从而中断或替换计算。

### 4.4 代数效应的优势

- 不用写 `Monad` 或 `Monad Transformer`。
- 效果可以按需组合。
- 处理顺序不同，语义不同。例如先处理状态再处理异常，和先处理异常再处理状态，可以得到不同恢复行为。
- 测试时可以替换 `IO`、数据库、日志等效果。

### 4.5 内建效果

| 效果 | 操作 | 说明 |
|---|---|---|
| `IO` | `println`, `readLine` | 外部输入输出 |
| `Error<e>` | `raise`, `catch` | 异常 |
| `State<s>` | `get`, `put` | 可变状态 |
| `Async` | `await` | 异步等待 |
| `NonDet` | `choice` | 非确定计算 |
| `Proc` | `spawn`, `send`, `receive` | 进程通信 |
| `STM` | `tvar`, `readTVar`, `writeTVar` | 软件事务内存 |

例如非确定计算：

```rune
effect Amb {
  flip() -> Bool
}

fn coin() -> Int effects {Amb} {
  if perform Amb.flip() then 1 else 0
}

handle {
  coin()
} with {
  Amb.flip() => resume(true) + resume(false)
}
// 结果可能是 1 和 0 的两种行为
```

---

## 5. 并发模型

Rune 提供轻量级 fiber，并通过效果系统约束并发副作用。

### 5.1 进程与消息

```rune
fn pingPong() -> Unit effects {IO, Proc} {
  let pid = spawn {
    receive {
      "ping" => println("pong")
      "stop" => println("bye")
      other  => println("received: " + other)
    }
  }

  send(pid, "ping")
  send(pid, "stop")
}
```

- `spawn` 创建 fiber。
- `send` 发送不可变消息。
- `receive` 阻塞直到消息匹配。
- 消息传递避免锁竞争。

### 5.2 软件事务内存

对于共享状态，Rune 提供 STM：

```rune
let accountA = tvar(100)
let accountB = tvar(50)

fn transfer(amount: Int) -> Unit effects {IO, STM} {
  atomically {
    let a = readTVar(accountA)
    let b = readTVar(accountB)
    writeTVar(accountA, a - amount)
    writeTVar(accountB, b + amount)
  }
}
```

`atomically` 支持自动重试和组合，避免死锁。

---

## 6. 求值策略

默认严格求值，惰性通过显式类型实现：

```rune
let nats = Stream.unfold(0, \n -> (n, n + 1))

nats
  |> Stream.filter(\x -> x % 2 == 0)
  |> Stream.take(5)
  |> Stream.toList
// 结果：[0, 2, 4, 6, 8]
```

`Stream` 是惰性、可记忆化的持久序列，适合无限数据和处理管道。

---

## 7. 类型推断

Rune 采用扩展 Hindley-Milner 类型推断，支持：

- 泛型自动泛化
- 记录行多态
- 效果行推导
- 局部类型推断

示例：

```rune
fn pipe(x, f, g) {
  g(f(x))
}
// 推断类型：
// fn pipe<a, b, c, e1, e2>(
//   x: a,
//   f: a -> b effects {e1},
//   g: b -> c effects {e2}
// ) -> c effects {e1, e2}
```

效果多态让高阶函数不会丢失或扩大副作用。

---

## 8. 模块系统

```rune
module Bank.Account

import Rune.Prelude
import Bank.Types

pub fn deposit(amount: Int) -> Int
  effects {State<Int>}
{
  let current = perform State.get()
  let next = current + amount
  perform State.put(next)
  next
}
```

- 模块与文件路径对应。
- 默认私有，`pub` 导出。
- 支持条件编译和测试模块。

---

## 9. 工具链

Rune 提供完整工具链：

```
rune init myproj
rune build
rune test
rune fmt
rune lsp
```

- `rune build` 可编译到原生二进制，也支持 `--target wasm`。
- LSP 提供类型信息、效果追踪、自动补全和重构。
- 包管理使用内容寻址依赖，构建可复现。

---

## 10. 完整示例：库存系统

结合效果、类型类与并发：

```rune
effect Db {
  queryStock(item: String) -> Int
  updateStock(item: String, newStock: Int) -> Unit
}

effect Audit {
  record(event: String) -> Unit
}

fn purchase(item: String, qty: Int) -> Bool
  effects {Db, Audit, Error<String>}
{
  perform Audit.record("purchase: " + item)

  let stock = perform Db.queryStock(item)

  if stock < qty then {
    perform Error.raise("not enough stock")
    false
  } else {
    perform Db.updateStock(item, stock - qty)
    true
  }
}

fn main() -> Unit effects {IO} {
  let result =
    handle {
      purchase("book", 3)
    } with {
      Db.queryStock(item) => {
        resume(5)
      }
      Db.updateStock(item, s) => {
        resume(())
      }
      Audit.record(event) => {
        println("AUDIT: " + event)
        resume(())
      }
      Error.raise(msg) => {
        println("ERROR: " + msg)
        false
      }
    }

  println("purchase result: " + boolToString(result))
}
```

这个例子中，数据库和审计逻辑完全被效果系统抽象。测试时可以替换成内存数据库或假审计处理器。

---

## 11. 与其他语言对比

| 特性 | Haskell | OCaml | Koka | Rune |
|---|---|---|---|---|
| 纯函数默认 | 是 | 否 | 是 | 是 |
| 副作用建模 | Monad | 无 | 代数效应 | 代数效应 |
| 默认求值 | 惰性 | 严格 | 严格 | 严格 |
| 行多态 | 部分 | 有 | 有 | 有 |
| 并发模型 | 多种 | 线程 | 有限 | fiber + STM |
| 类型推断 | 全局 | 全局 | 全局 | 全局 |

Rune 的核心差异在于：**并发和副作用被统一在效果系统中，用户不必在单子和直接副作用之间做选择**。

---

## 12. 未来方向

- **形式化内核**：Rune Core 可被证明类型安全。
- **依赖类型片段**：为长度、索引等不变量提供更细粒度类型。
- **编译器插件**：允许用户编写自定义优化 pass。
- **分布式效果**：将代数效应扩展到多节点环境。

---

以上是 Rune 的设计概要。它试图在 Haskell 的严谨、OCaml 的实用、Koka 的效果表达力之间找到一个新的平衡点。
