# [v2:deepseek-flash] 任务1 函数式编程语言 | 条件: baseline | 第 7 次

**Prompt:** 设计一个全新的函数式编程语言

**耗时:** 36.25s | tokens: 37/7114

---

下面给出一份可落地的“全新函数式编程语言”设计草案。工作名：**Luma（流明语）**，文件后缀 `.luma`。

---

## 1. 定位

**Luma 是一门纯函数为默认、效果显式、静态强类型、适合并发与工具化的现代函数式语言。**

一句话概括：

> 用不可变值和代数数据类型表达业务逻辑，用显式效果行描述副作用，用 handler 把效果解释成具体行为。

设计原则：

1. **纯核心**：普通函数默认无副作用，副作用必须通过 `effect` 声明。
2. **表达式一切**：`if`、`match`、块、`handle` 都产生值。
3. **不可变优先**：所有绑定默认不可变，持久化数据结构为主。
4. **类型系统实用**：HM 推断 + 双向检查、ADT、记录行多态、trait、效果行。
5. **严格求值 + 显式惰性**：默认 call-by-value，需要时使用 `lazy`。
6. **工具链优先**：格式化、LSP、包管理、文档、测试从第一天就是一等公民。

---

## 2. 基础语法

### 2.1 模块与定义

```luma
module Main

use Std.{Unit, String, Int, List, Option}

pub def add(x: Int, y: Int): Int =
  x + y

def id[a](x: a): a =
  x
```

约定：

- 使用大括号 `{}`，不依赖缩进。
- 表达式末尾不需要分号。
- `pub` 导出，默认模块内可见。
- 泛型参数写在名字后的 `[...]` 中。

### 2.2 代数数据类型

```luma
type Option[a] = Some(a) | None

type Result[e, a] = Ok(a) | Err(e)

type Tree[a] =
  | Leaf
  | Node(Tree[a], a, Tree[a])
```

模式匹配必须覆盖所有情况，否则编译错误：

```luma
def orElse[a](opt: Option[a], default: a): a =
  match opt {
    Some(x) => x
    None    => default
  }
```

### 2.3 记录与行多态

```luma
type User = {
  name: String,
  age: Int
}

def birthday(u: User): User =
  { u with age = u.age + 1 }
```

记录类型支持行多态：

```luma
def getName[r](u: { name: String | r }): String =
  u.name
```

### 2.4 函数与管道

```luma
def inc(x: Int): Int = x + 1

let f = (x: Int) => x * 2

let result =
  10
  |> inc
  |> f
```

---

## 3. Trait 与泛型

Luma 用 trait 表达类型类式抽象：

```luma
trait Show[a] {
  def show(x: a): String
}

impl Show[Int] {
  def show(x: Int): String =
    Int.to_string(x)
}

def display[a: Show](x: a): String =
  Show.show(x)
```

约束：

- 默认全局一致性：禁止孤儿实例，避免同一类型存在多个冲突实例。
- trait 可组合，支持默认实现。
- 公开 API 建议标注类型；局部变量可完全推断。

---

## 4. 效果系统

这是 Luma 的核心特色。

### 4.1 声明效果

```luma
effect Console {
  print: String -> Unit
}
```

函数类型中用 `/ {效果行}` 表示副作用：

```luma
def greet(name: String): Unit / {Console} =
  Console.print("Hello, " ++ name ++ "!")
```

纯函数省略效果行，等价于 `/ {}`。

### 4.2 效果行多态

```luma
def map[a, b, e](f: a -> b / e, xs: List[a]): List[b] / e =
  match xs {
    Nil     => Nil
    x :: xs => f(x) :: map(f, xs)
  }
```

`map` 不关心 `f` 是否有副作用；有什么效果就传播什么效果。

### 4.3 Handler

效果由 handler 解释：

```luma
handler consoleToStdout = {
  print(msg, k) => {
    Stdout.writeLine(msg)
    k(())
  }
}

def main(): Unit =
  handle greet("Luma") with consoleToStdout
```

语义上：

- `Console.print` 触发 `print` 操作。
- handler 接收参数 `msg` 和续延 `k`。
- `k(())` 恢复被挂起的计算。
- 普通代码不能直接执行底层 IO；入口点由运行时提供最终 handler。

默认 handler 是单次恢复的，便于高性能实现；需要多分支探索时可显式声明 `multi handler`。

---

## 5. 类型系统设计

核心类型：

```text
τ ::= Int
    | Bool
    | String
    | Unit
    | a
    | List τ
    | Option τ
    | Result ε τ
    | { field: τ, ... | ρ }       // 记录与行多态
    | τ -> τ / E                   // 带效果行的函数
    | ...

E ::= {} | { Effect | E }
```

特性：

- HM 风格类型推断，加双向类型检查。
- 顶层公开定义要求或强烈建议标注类型。
- ADT 与模式匹配做穷尽性检查。
- 记录支持行多态。
- 函数支持效果行多态。
- 无 `null`，空值用 `Option[a]`。
- 可变性通过独立类型表达，例如 `Ref[a]`，且它本身也是一个效果。

---

## 6. 求值与运行时语义

- **严格求值**：默认 call-by-value，容易预测性能。
- **显式惰性**：`lazy expr : Lazy[a]`，用 `force` 求值。
- **尾调用优化**：尾递归和尾调用保证常量栈空间。
- **不可变值**：持久化 List、Map、Set；底层可用结构共享。
- **GC**：分代 GC + 逃逸分析；未来可加入唯一性/线性类型优化。
- **效果语义**：基于代数效果与 delimited continuation；单次续延优先优化。
- **并发模型**：结构化并发，`Async` 作为效果，`scope` 限定任务生命周期。

示例：

```luma
def fetchAll(urls: List[String]): List[Response] / {Http, Async} =
  scope {
    urls
    |> List.map((url) => async { Http.get(url) })
    |> List.map(Task.await)
  }
```

---

## 7. 标准库与工具链

Prelude 包括：

- 基础类型：`Int`、`Float`、`Bool`、`String`、`Unit`
- 容器：`List`、`Array`、`Map`、`Set`
- 错误处理：`Option`、`Result`
- 常用 trait：`Eq`、`Ord`、`Show`、`Semigroup`、`Monoid`、`Functor`、`Foldable`
- 并发：`Task`、`Async`、`scope`
- 常用效果：`Console`、`File`、`Http`、`Random`、`State`

工具：

```bash
luma new myapp
luma run
luma test
luma fmt
luma doc
luma repl
luma lsp
```

编译器建议分阶段实现：

1. 手写 lexer/parser。
2. 双向类型检查 + 行统一。
3. 效果推导与 handler 展开。
4. Core IR：带效果操作的 lambda calculus。
5. ANF/CPS 变换。
6. 后端：先解释器，再 WASM/LLVM。

---

## 8. 完整示例

```luma
module Main

use Std.{Unit, String, Int}

effect Console {
  print: String -> Unit
}

trait Show[a] {
  def show(x: a): String
}

impl Show[Int] {
  def show(x: Int): String =
    Int.to_string(x)
}

type Tree[a] =
  | Leaf
  | Node(Tree[a], a, Tree[a])

def mapTree[a, b](f: a -> b, t: Tree[a]): Tree[b] =
  match t {
    Leaf          => Leaf
    Node(l, x, r) => Node(mapTree(f, l), f(x), mapTree(f, r))
  }

def sum(t: Tree[Int]): Int =
  match t {
    Leaf          => 0
    Node(l, x, r) => sum(l) + x + sum(r)
  }

def greet(name: String): Unit / {Console} =
  Console.print("Hello, " ++ name)

handler consoleToStdout = {
  print(msg, k) => {
    Stdout.writeLine(msg)
    k(())
  }
}

def main(): Unit =
  handle {
    let t = Node(Leaf, 1, Node(Leaf, 2, Leaf))
    let t2 = mapTree((x: Int) => x * 2, t)
    Console.print(Int.to_string(sum(t2)))
    greet("Luma")
  } with consoleToStdout
```

这个程序展示了 Luma 的几个核心点：不可变树、ADT、模式匹配、trait、显式效果和 handler。

---

## 9. 设计取舍

- **纯函数默认**让代码更可推理，但初学者需要理解效果系统。
- **效果行**比直接使用 monad transformer 更自然，但类型统一和编译优化更复杂。
- **严格求值**利于性能和调试，但需要 `lazy` 支持惰性结构。
- **trait 全局一致性**保证可预测性，但会限制某些灵活实例写法。
- **结构化并发**降低并发错误，但需要运行时调度器支持。

如果继续推进，下一步应该先写一份正式语言规范：词法、语法、类型规则、操作语义、效果 handler 语义，然后实现一个最小解释器。
