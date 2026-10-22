# [v2:deepseek-flash] 任务1 函数式编程语言 | 条件: baseline | 第 3 次

**Prompt:** 设计一个全新的函数式编程语言

**耗时:** 45.13s | tokens: 37/8290

---

我设计一门名为 **Weft（纬）** 的函数式编程语言。  
口号是：**“纯函数为经，显式效果为纬。”**  
它不是 Haskell/OCaml 的简单方言，而是一门以 **显式代数效应、行多态、能力安全、单次续延** 为核心的语言。

---

## 1. 设计目标

1. **默认纯函数**：普通表达式无副作用，可安全重排、缓存、并行。
2. **副作用显式进入类型**：所有 IO、状态、异常、并发都通过代数效应表示。
3. **无环境权限**：没有隐式全局 `IO`；真实权限只能由运行时能力显式授予。
4. **结构化数据优先**：记录、变体、模式匹配、行多态。
5. **可预测执行**：严格求值、穷尽性检查、单次续延默认、确定性错误。
6. **小核心 + 可降级语法糖**：核心语言可形式化，表层语法友好。

---

## 2. 快速语法预览

```weft
module Demo

type List<A> =
  | Nil
  | Cons(A, List<A>)

fn map<A, B>(f: A -> B, xs: List<A>): List<B> =
  match xs {
    Nil         => Nil,
    Cons(x, xs) => Cons(f(x), map(f, xs))
  }
```

说明：

- `fn` 定义函数，顶层函数默认可递归。
- 纯函数不写效果；完整写法是 `... -> B ! {}`。
- `match` 必须穷尽。
- 列表、可选值等只是库类型，不是特殊魔法。

记录是结构化的，并支持行多态：

```weft
fn nameOf(p: { name: String, ...r }): String =
  p.name

let p = { name = "Ada", age = 36 }
```

---

## 3. 代数效应系统

效果声明：

```weft
effect Console {
  op readLine(): String
  op println(msg: String): Unit
}
```

函数类型用 `!` 标注效果行：

```weft
fn greet(): Unit ! { Console } =
  let name = Console.readLine()
  Console.println("Hello, " ++ name)
```

`! { Console }` 表示调用 `greet` 可能执行 `Console` 效果。纯函数写成：

```weft
fn add(x: Int, y: Int): Int ! {} = x + y
```

也可以省略 `! {}`：

```weft
fn add(x: Int, y: Int): Int = x + y
```

效果由 handler 消除：

```weft
fn pureGreet(): Unit ! {} =
  handle greet() {
    Console.readLine(resume) => resume("Ada")
    Console.println(msg, resume) => resume(())
  }
```

这里：

- `resume` 表示继续被处理的计算。
- `Console.readLine` 的结果类型是 `String`，所以 handler 中写 `resume("Ada")`。
- `Console.println` 的结果类型是 `Unit`，所以写 `resume(())`。

关键语义选择：

- **默认单次续延**：`resume` 最多调用一次，保证资源安全。
- 需要多次续延的 handler 必须显式声明为 `multishot handler`，并受线性能力约束。
- handler 是词法作用域的，效果行静态跟踪。
- 没有 `unsafePerformIO`；真实 IO 只能由入口运行时安装的能力 handler 提供。

---

## 4. 类型系统

核心类型大致为：

```text
τ ::= Int | Float | Bool | String | Unit
    | τ1 -> τ2 ! ρ
    | { l: τ, ... }
    | C<τ...>
    | α

ρ ::= {} | { E | ρ } | ρvar
```

其中：

- `ρ` 是效果行。
- `{}` 表示纯。
- `{ Console | ρ }` 表示至少包含 `Console` 的开放效果行。
- 记录行和效果行共用同一套行多态机制，便于写通用 handler 和通用记录操作。

类型检查采用：

- 双向类型检查。
- 局部类型推导。
- 行统一。
- 模块边界要求显式函数签名。
- 模式匹配穷尽性和冗余性检查。
- 不引入全局 typeclass 实例；多态接口用显式字典值或 `using` 语法糖传递，避免全局实例搜索和隐式全局状态。

例如接口值：

```weft
interface Eq<A> {
  eq: (A, A) -> Bool
}

fn contains<A>(dict: Eq<A>, x: A, xs: List<A>): Bool =
  match xs {
    Nil         => false,
    Cons(y, ys) => dict.eq(x, y) || contains(dict, x, ys)
  }
```

`using Eq<A>` 只是自动插入显式参数，不做全局实例查找。

---

## 5. 求值与语义

Weft 采用：

- 严格求值，call-by-value。
- 表达式，无语句；`let` 不可变。
- 递归、模式匹配、代数数据类型。
- 效果调用通过 handler 解释为带界续延。
- 无异常机制；错误用 `Result<E, A>` 表示。
- 无 `null`；可选值用 `Option<A>`。
- 值不可变；需要状态时使用 `State<S>` 效果，由 handler 管理。

核心 IR 可以设计为：

```text
CoreWeft = ANF + 显式 handler + 单次续延
```

这样便于：

- 解释执行。
- 编译到 WASM。
- 后续接 LLVM 后端。
- 分析效果行和续延使用。

---

## 6. 能力安全

Weft 区分“效果”和“能力”。

- 效果是类型层面的可能行为，例如 `Console`。
- 能力是运行时实际权限，例如 `RuntimeConsole`。
- 用户代码不能凭空获得真实 IO 权限。
- 入口点由运行时安装顶层 handler。

示例：

```weft
fn main(): Unit ! { Console } =
  greet()
```

运行时负责为 `main` 提供 `Console` handler。库代码只能看到效果，不能直接访问操作系统。

未来可加入线性能力：

```weft
Ref.new(0)      : Int -> Ref<Int>
Ref.read(r)     : Ref<Int> -> Int ! { State }
Ref.write(r, v) : (Ref<Int>, Int) -> Unit ! { State }
```

能力值不可复制，只能线性传递，避免共享可变状态泄漏。

---

## 7. 并发模型

并发不是内建语法，而是一个库效果：

```weft
effect Par {
  op spawn<A>(task: () -> A ! e): Task<A>
  op await<A>(task: Task<A>): A
  op cancel(task: Task<A>): Unit
}
```

推荐结构化并发：

```weft
par {
  let t1 = spawn(fetchA)
  let t2 = spawn(fetchB)
  await(t1) + await(t2)
}
```

`par` 作用域退出时保证：

- 所有子任务已结束或被取消。
- 不泄漏后台线程。
- 父子任务效果行可静态分析。

---

## 8. 模块与工具链

模块示例：

```weft
module Main

import Data.List (map)
import Console

export main

fn main(): Unit ! { Console } =
  Console.println("Hello, Weft")
```

工具链设计：

- `weftc`：编译器。
- `weft repl`：交互式解释器。
- `weft fmt`：格式化器。
- `weft lsp`：语言服务器。
- `weft pkg`：包管理器。
- 测试框架支持属性测试和 handler 级 mock。

编译流水线：

```text
源码 -> 解析 -> 名称解析 -> 类型/效果推断 -> CoreWeft
     -> 优化 -> 解释器 / WASM / LLVM
```

---

## 9. 一个完整示例

```weft
module Main

type Result<E, A> =
  | Ok(A)
  | Err(E)

effect Console {
  op readLine(): String
  op println(msg: String): Unit
}

fn greet(): Unit ! { Console } =
  let name = Console.readLine()
  Console.println("Hello, " ++ name)

fn mockGreet(): Unit ! {} =
  handle greet() {
    Console.readLine(resume) => resume("Ada")
    Console.println(msg, resume) => resume(())
  }

fn main(): Unit ! { Console } =
  greet()
```

`mockGreet` 是纯的，因为 `Console` 被 handler 消除了。  
`main` 仍然有 `Console` 效果，因为真实运行环境由入口运行时处理。

---

## 10. Weft 的新颖点总结

1. **效果行 + 能力安全**：副作用不仅出现在类型中，还要求运行时显式授权。
2. **默认单次续延的代数效应**：资源安全、实现高效；多次续延必须显式声明。
3. **记录行、变体行、效果行统一为行多态机制**：handler 和记录操作共享同一套类型基础设施。
4. **无全局 typeclass 实例**：多态通过显式字典传递，避免隐式全局状态。
5. **结构化并发作为库效果**：不污染核心语言，又能保证任务生命周期。
6. **小核心、可形式化、可编译到 WASM/LLVM**：适合教学、研究和工业实验。

一句话概括：**Weft 是一门以纯函数为默认、以显式效果和能力安全为骨架、以单次续延为效率保障的现代函数式语言。**
