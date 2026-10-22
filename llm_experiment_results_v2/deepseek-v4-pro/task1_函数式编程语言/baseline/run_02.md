# [v2:deepseek-v4-pro] 任务1 函数式编程语言 | 条件: baseline | 第 2 次

**Prompt:** 设计一个全新的函数式编程语言

**耗时:** 178.76s | tokens: 90/12618

---

# Mira：一门全新的纯函数式编程语言设计

我把这门语言命名为 **Mira**。它是一门概念上的新语言，设计目标是把“纯函数式编程”“显式效应”“结构化并发”和“轻量依赖类型”组合成一个可读、可推理、可工程化的整体。

---

## 1. 设计定位

Mira 不是 Haskell、Elm、Koka、Idris 的方言，而是一门重新设计的语言。

核心原则：

- **纯函数核心**：默认不可变，函数调用无隐藏副作用。
- **副作用即效应**：所有与环境交互的操作都通过“代数效应”显式表达。
- **类型尽量强，但不折磨人**：支持完整类型推断、行多态、轻量依赖类型。
- **并发是一等公民**：内建结构化并发、监督树和消息传递。
- **可预测性优先**：严格求值，不用隐式惰性。
- **可观测性优先**：因为副作用必须经过效应操作，所以运行时天然可以记录、追踪、回放。

---

## 2. 语言特性总览

### 2.1 基础语法

Mira 使用缩进敏感语法，风格接近 Elm、Lean、Roc 的混合体。

```mira
module Main

import Mira.Console

fn main() ! Console =
  perform Console.print "Hello, world!"
```

函数的类型签名使用 `fn`：

```mira
fn add(x: Int, y: Int) -> Int =
  x + y
```

多泛型参数使用小写字母自动推断：

```mira
fn identity(x: a) -> a =
  x
```

### 2.2 代数数据类型与模式匹配

```mira
type Option a =
  | Some a
  | None

type Tree a =
  | Leaf
  | Node (Tree a) a (Tree a)

fn sum(tree: Tree Int) -> Int =
  match tree {
    Leaf => 0
    Node(left, x, right) => sum(left) + x + sum(right)
  }
```

模式匹配可以带守卫：

```mira
fn find(p: fn(a) -> Bool, xs: List a) -> Option a =
  match xs {
    Nil => None
    Cons(x, _) if p(x) => Some x
    Cons(_, rest) => find(p, rest)
  }
```

---

## 3. 类型系统

Mira 的类型系统主要有四层：

### 3.1 基础类型

- `Int`、`Float`、`String`、`Bool`、`Unit`
- `Never`：表示不可能返回的类型
- `List a`、`Option a`、`Result e a`
- 元组 `(a, b, c)`

### 3.2 代数数据类型

所有自定义类型都是 ADT，编译器会自动生成结构比较、模式匹配优化和序列化支持。

### 3.3 行多态记录

Mira 的记录是开放的，适合写通用代码。

```mira
fn greet(person: {| name: String |}) ! Console =
  perform Console.print ("Hello, " ++ person.name)

let ada = { name = "Ada", age = 36 }
greet(ada)
```

`{| name: String |}` 表示“至少有 `name` 字段”的记录类型。更新记录使用：

```mira
let older = { ada | age = 37 }
```

### 3.4 轻量依赖类型

Mira 支持有限的依赖类型，主要用于长度、索引和资源约束。

例如，长度安全的向量：

```mira
type Vec a (n : Nat) =
  | Nil : Vec a 0
  | Cons (a) (Vec a n) : Vec a (n + 1)

fn zip(a: Vec a n, b: Vec b n) -> Vec (a, b) n =
  match (a, b) {
    (Nil, Nil) => Nil
    (Cons(x, xs), Cons(y, ys)) => Cons((x, y), zip(xs, ys))
  }
```

这保证两个向量长度相同时才可以 `zip`，避免运行时越界。

---

## 4. 效应系统

Mira 最核心的设计是“代数效应”。

### 4.1 定义效应

```mira
effect Console {
  fn print(msg: String) -> Unit
  fn input(prompt: String) -> String
}
```

### 4.2 执行效应

调用效应必须使用 `perform`：

```mira
fn askName() ! Console =
  let name = perform Console.input "What is your name?"
  perform Console.print ("Hello, " ++ name)
```

函数的效应行写在返回类型之后：

```mira
fn askName() -> String ! Console
```

多个效应使用 `! { ... }`：

```mira
effect Random {
  fn intBetween(low: Int, high: Int) -> Int
}

fn rollDice() -> Int ! { Console, Random } =
  let n = perform Random.intBetween(1, 6)
  perform Console.print ("You rolled: " ++ toString n)
  n
```

### 4.3 处理效应

效应处理器的形式类似模式匹配，但它可以控制后续计算。

```mira
handler terminalHandler = {
  print(msg) -> k =>
    nativePrintLine(msg)
    k(())

  input(prompt) -> k =>
    nativePrintLine(prompt)
    k(nativeReadLine())
}

fn main() =
  handle askName() with terminalHandler
```

`k` 是 continuation。处理器可以选择：

- 调用 `k` 一次，正常继续；
- 调用 `k` 多次，实现重试；
- 不调用 `k`，中断计算；
- 转换结果后再继续。

例如，给 HTTP 请求加重试效应的处理器：

```mira
effect HTTP {
  fn get(url: String) -> String
}

handler retryHandler(times: Nat) = {
  get(url) -> k =>
    loop(times) {
      result = k(perform HTTP.get(url))
      if nonEmpty(result) then result
      else continue
    }
}
```

这种能力使得错误处理、依赖注入、超时、限流、追踪都变成可组合的普通代码，而不需要 monad transformer。

---

## 5. 并发模型

Mira 的并发不是“共享内存 + 锁”，而是：

- 轻量任务 `Task a`
- 结构化并发：`spawn` / `awaitAll`
- 进程 + 消息传递
- 监督树

### 5.1 轻量任务

```mira
fn fetchAll(urls: List String) -> List String ! { HTTP, Process } =
  urls
  |> map(fn url => spawn { HTTP.get(url) })
  |> awaitAll
```

`spawn` 创建一个 `Task a`，`awaitAll` 等待所有任务完成。任务之间不共享可变状态，只通过返回值或消息通信。

### 5.2 进程与消息

```mira
type Message =
  | Stop
  | Work(String)

fn worker() ! Process =
  loop {
    msg = perform Process.receive()
    match msg {
      Stop => return ()
      Work(text) => perform Process.send(workerResult(text))
    }
  }
```

### 5.3 监督树

每个进程都由监督者管理，支持崩溃恢复：

```mira
supervisor {
  children = [worker, worker, worker]
  policy = Restart(limit = 5, backoff = 2.seconds)
}
```

这提供了类似 Erlang/OTP 的容错能力，但语法更现代。

---

## 6. 模块系统

Mira 的模块是一等公民，可以定义模块签名和模块函子。

### 6.1 模块签名

```mira
module Math.Algebra

signature Ring(a) = {
  zero: a
  add: fn(a, a) -> a
  mul: fn(a, a) -> a
}
```

### 6.2 模块实现

```mira
module IntRing : Ring(Int) = {
  zero = 0
  add = fn(x, y) => x + y
  mul = fn(x, y) => x * y
}
```

### 6.3 模块函子

```mira
module MakeList(Item: Comparable) : ListModule(Item) = {
  sort = ...
}
```

模块系统允许大规模代码组织，同时保持依赖注入和单元测试的便利性。

---

## 7. 工具链与生态

Mira 的参考编译器设计为多个后端：

- **原生后端**：基于 LLVM
- **Web 后端**：WebAssembly
- **可选嵌入式后端**：用于脚本和边缘计算

工具链包括：

```bash
mira init           # 创建项目
mira fmt            # 格式化
mira check          # 类型检查
mira build          # 构建
mira test           # 测试
mira doc            # 生成文档
mira repl           # 交互式环境
mira replay         # 回放效应日志
```

`mira replay` 是 Mira 的特色：因为所有副作用都通过效应操作，编译器可以记录效应事件流，开发者可以像回放录屏一样回放一次程序执行，用于调试并发问题和定位 flaky tests。

---

## 8. 完整示例：转账领域模型

下面展示一个更完整的示例，结合效应、依赖类型和模块：

```mira
module Bank.Transfer

import Mira.Result
import Mira.Nat

type Account = {
  id: AccountId,
  balance: Money,
}

effect Ledger {
  fn debit(account: Account, amount: Money) -> Unit
  fn credit(account: Account, amount: Money) -> Unit
}

effect Failure {
  fn abort(msg: String) -> Never
}

fn transfer(from: Account, to: Account, amount: Money)
  -> Unit ! { Ledger, Failure } =
  if amount <= 0 then
    perform Failure.abort "转账金额必须大于零"
  else
    perform Ledger.debit(from, amount)
    perform Ledger.credit(to, amount)
```

调用时，外部注入不同的 `Ledger` 处理器：

```mira
fn main() =
  handle
    transfer(alice, bob, 100)
  with inMemoryLedger()
```

测试时可以替换为 mock 处理器，生产环境可以替换为数据库处理器，而不修改业务函数本身。

---

## 9. 与其他语言的区别

| 特性 | Haskell | Elm | Rust | Koka | Mira |
|------|---------|-----|------|------|------|
| 纯函数 | 是 | 是 | 否 | 是 | 是 |
| 副作用建模 | Monad | Cmd | Unsafe 块 | Effect | Effect rows |
| 行多态记录 | 有限 | 是 | 无 | 有限 | 一等 |
| 依赖类型 | 有限 | 无 | 无 | 无 | 轻量 |
| 结构化并发 | 一般 | Task | async | 有限 | 内建监督树 |
| 效应回放调试 | 否 | 否 | 否 | 部分 | 是 |
| 默认求值顺序 | 惰性 | 严格 | 严格 | 严格 | 严格 |

Mira 的独特之处不是发明每一项特性，而是把它们放在一个统一的类型系统和效应系统中：

- 效应行让副作用组合变得简单；
- 行多态让记录操作更灵活；
- 轻量依赖类型消除了大量运行时错误；
- 监督树让并发系统真正可维护。

---

## 10. 设计取舍

Mira 有意做出以下取舍：

1. **严格求值，而不是惰性求值**  
   性能更可预测，也更容易与效应系统结合。需要惰性时，使用显式 `Lazy` 类型。

2. **效应系统，而不是 monad 作为核心抽象**  
   monad 在库中仍可使用，但语言层面不强制用户理解 `Monad`、`MonadTransformer`。

3. **不提供任意宏**  
   第一版语言不支持宏，只提供 `deriving` 和可预测的代码生成。宏系统往往破坏可读性和工具链质量。

4. **不追求完全依赖类型**  
   完全依赖类型和证明系统会让语言更难学。Mira 只做长度、索引和有限资源约束。

5. **默认使用追踪 GC**  
   Mira 不追求无 GC 的系统编程，而是通过持久化数据结构、任务隔离和可预测停顿来管理内存。

---

## 总结

Mira 是一个“纯函数式 + 显式效应 + 结构化并发 + 轻量依赖类型”的新语言设计。它试图解决传统函数式语言的两个痛点：

- 副作用管理过于复杂；
- 并发与错误处理不够工程化。

它不是现有语言的简单组合，而是一次重新组织语言核心抽象的尝试。

如果你愿意，我可以继续展开：

- Mira 的形式化类型规则；
- 效应行与类型推断算法；
- 标准库设计；
- 编译器实现路线图；
- 更多真实项目示例。
