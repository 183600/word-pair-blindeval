# [v2:deepseek-v4-pro] 任务1 函数式编程语言 | 条件: baseline | 第 7 次

**Prompt:** 设计一个全新的函数式编程语言

**耗时:** 90.41s | tokens: 90/6603

---

下面是一套全新的函数式编程语言设计方案，暂定名 **Liora**（光语）。  
它不是一个现有语言的方言，而是一门从核心语法、类型系统、副作用管理到并发模型都重新设计的语言。

---

## 一、设计哲学

Liora 的核心目标是：

- **纯函数式**：默认不可变，所有计算都是表达式。
- **强静态类型**：全局类型推断，类型错误在编译期发现。
- **显式副作用**：所有可能产生效果的函数都必须在类型签名中声明。
- **可组合并发**：基于轻量进程、消息传递和结构化并发。
- **人类可读**：语法接近 Python/Elixir，但具备 Haskell/ML 的表达能力。
- **可预测性**：没有 `null`，没有未处理异常，没有隐式全局状态。

---

## 二、核心语法

Liora 采用缩进敏感语法，所有代码块都是表达式。

### 1. 函数与管道

```liora
-- 注释用 --

module Geometry

import Liora/Prelude

-- 类型签名
area : Shape -> Float
area = cases
  Circle r      -> pi * r * r
  Rectangle w h -> w * h
  Group shapes  -> shapes |> map area |> sum
```

函数默认自动柯里化：

```liora
add : Int -> Int -> Int
add x y = x + y

increment : Int -> Int
increment = add 1
```

管道运算符 `|>` 让数据流更清晰：

```liora
result =
  [Circle 2, Rectangle 3 4, Circle 5]
  |> map area
  |> sum
```

### 2. 代数数据类型

```liora
type Shape
  = Circle Float
  | Rectangle Float Float
  | Group [Shape]
```

模式匹配是唯一解构方式：

```liora
describe : Maybe Int -> String
describe = cases
  Just n  -> "value: " ++ show n
  Nothing -> "empty"
```

### 3. 记录与行多态

```liora
type User = {
  name : String,
  age  : Int,
  tags : [String]
}

ada : User
ada = { name = "Ada", age = 36, tags = ["math", "logic"] }

-- 行多态：只要求记录中有 name 字段
getName : { name : String | r } -> String
getName user = user.name
```

`{ name : String | r }` 表示“至少含有 `name` 字段的记录类型”，其余字段通过行变量 `r` 保留。

---

## 三、类型系统

Liora 的类型系统由四层组成：

### 1. 参数多态

类似 ML 的泛型：

```liora
map : (a -> b) -> [a] -> [b]
map f xs = cases
  []      -> []
  x :: xs -> f x :: map f xs
```

### 2. 行多态

用于记录和变体，避免过度限制。

### 3. 类型类

用于可重载操作和接口抽象：

```liora
class Show a where
  show : a -> String

instance Show User where
  show user = user.name ++ "#" ++ show user.age
```

### 4. 可选依赖类型

Liora 允许在需要时使用依赖类型，表达更强的不变量：

```liora
type Vec : Nat -> Type -> Type
  = Nil  : Vec 0 a
  | Cons : a -> Vec n a -> Vec (n + 1) a

-- 这个函数永远不会对空列表调用
head : Vec (n + 1) a -> a
head (Cons x _) = x
```

`head Nil` 是编译错误，因为 `Nil` 的长度为 0，不满足 `n + 1`。

---

## 四、效果系统：代数效应取代单子

Liora 不使用 Monad 变换器，而是采用 **代数效应** 来显式管理副作用。

### 定义效果

```liora
effect Console {
  emit : String -> Unit
}
```

### 使用效果

函数类型签名中必须写明它可能执行的效果：

```liora
greet : String -> Unit / { Console }
greet name = do
  Console.emit("Hello, " ++ name)
```

### 处理效果

调用者必须提供效果处理器：

```liora
main : Unit / { IO }
main = handle
  greet "Ada"
with
  Console.emit msg -> IO.println(msg); continue ()
```

其中 `continue` 会恢复被中断的计算。

### 可恢复效果

代数效应可以用于实现可恢复的异常、非确定性计算、依赖注入等：

```liora
effect Ask {
  ask : String -> Int
}

compute : Int / { Ask }
compute = do
  x <- Ask.ask "x"
  y <- Ask.ask "y"
  pure (x + y)

main = handle compute with
  Ask.ask "x" -> resume 10
  Ask.ask "y" -> resume 20
```

这里 `resume 10` 表示用值 10 恢复计算，得到最终结果 30。

与 Monad 相比，代数效应更容易组合，不会出现“单子变换器堆叠”问题。

---

## 五、并发模型

Liora 采用 **轻量进程 + 消息传递 + 结构化并发**。

### 进程与邮箱

```liora
type Message
  = Inc Int
  | Get (Mailbox Int)

counter : Mailbox Message -> Unit / { Async }
counter mb = loop 0 where
  loop n = do
    msg <- receive mb
    case msg of
      Inc i -> loop (n + i)
      Get reply -> do
        send reply n
        loop n

main : Unit / { IO, Async }
main = do
  mb <- newMailbox
  spawn (counter mb)

  send mb (Inc 10)
  send mb (Inc 5)

  reply <- newMailbox
  send mb (Get reply)
  result <- receive reply

  IO.println(show result)  -- 输出 15
```

### 结构化并发

父进程可以等待子进程完成，并自动传播取消信号：

```liora
parent : Unit / { Async }
parent = do
  child <- spawn worker
  await child
```

没有“孤儿进程”，并发行为可预测。

### 可选 STM

对于需要共享状态的场景，Liora 提供软件事务内存：

```liora
account : TVar Int -> TVar Int -> Int -> Unit / { STM }
account from to amount = do
  modify from (\v -> v - amount)
  modify to   (\v -> v + amount)
```

事务失败会自动重试，避免锁和竞态。

---

## 六、模块系统

模块名与文件路径对应，支持显式导出：

```liora
module Geometry export (Shape(..), area)

type Shape
  = Circle Float
  | Rectangle Float Float
  | Group [Shape]

area : Shape -> Float
area = cases
  Circle r      -> pi * r * r
  Rectangle w h -> w * h
  Group shapes  -> shapes |> map area |> sum
```

导入时可以精确选择符号：

```liora
import Geometry (Shape(..), area)
import Liora/Console as Console
```

---

## 七、工具链设计

Liora 配套工具链：

- `liorac`：编译器，可编译为原生代码、WASM、JavaScript。
- `liora repl`：交互式解释器。
- `liorafmt`：自动格式化。
- `liora test`：内置测试框架。
- `lsp`：语言服务器，支持 IDE 集成。
- 包管理器：支持语义化版本和可复现构建。

---

## 八、完整示例：并发下载器

下面是一个更真实的示例，展示 Liora 的效果、并发和错误处理如何协同工作：

```liora
module Downloader

import Liora/HTTP
import Liora/Async
import Liora/IO

effect Retry {
  retry : String -> Unit
}

fetch : String -> String / { HTTP, Retry, IO }
fetch url = do
  response <- HTTP.get url
  case response.status of
    200 -> pure response.body
    503 -> do
      Retry.retry url
      fetch url
    _ -> fail ("Bad status: " ++ show response.status)

worker : String -> Mailbox (String, String) -> Unit / { HTTP, Retry, IO, Async }
worker url out = do
  body <- fetch url
  send out (url, body)

main : Unit / { IO, Async }
main = do
  urls <- IO.readFile "urls.txt"
  out <- newMailbox

  for urls (\url -> spawn (worker url out))

  results <- collect (length urls) out
  IO.println("Downloaded " ++ show (length results) ++ " pages")
```

这里的 `Retry` 是一种可恢复效应，上层处理策略可以决定是否重试、延迟、记录日志，而下载逻辑不需要知道这些细节。

---

## 九、与现有语言的差异

| 特性 | Haskell | OCaml | Elixir | Liora |
|------|---------|-------|--------|-------|
| 副作用管理 | Monad | 不显式 | 不显式 | 代数效应 |
| 并发模型 | 异步/绿线程 | 线程/域 | Actor | 轻量进程 + 结构化并发 |
| 类型系统 | HM + 类型类 | HM + 模块 | 动态 | HM + 行多态 + 依赖类型 |
| 空值处理 | Maybe | Option | nil | 无 null，ADT |
| 语法风格 | 简洁但抽象 | 相对传统 | 友好 | 友好且表达式优先 |

---

## 十、总结

Liora 的设计亮点是：

1. **代数效应** 取代 Monad，让副作用显式、可组合、可恢复。
2. **行多态 + 依赖类型** 在灵活性和安全性之间取得平衡。
3. **结构化并发** 避免资源泄漏和不可控进程。
4. **默认不可变 + 全局类型推断** 让代码既安全又简洁。
5. **无 null、无未处理异常、无隐式全局状态**，程序行为可预测。

这只是一个概念设计，但它展示了一种可能性：未来的函数式语言可以同时具备 Haskell 的类型安全、Elixir 的并发亲和力，以及 Python 般可读的语法。
