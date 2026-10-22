# [v2:deepseek-v4-pro 评 deepseek-flash] task1 函数式编程语言 | run 2 | swap=True

**Winner:** baseline (raw=B)

**A:** cleaned_word_pairs | **B:** baseline

---

## 回答 A

# 新语言：澜织 Loomi

**Loomi 是一门纯函数为默认、效应显式、类型即契约、并发结构化、运行时可重放的函数式编程语言。**

## 1. 设计概念与语言映射

| 设计说明 |
|---|
| 纯核心与副作用边界：效应必须显式隔离 |
| 可组合、可解释的效应：效应行 `Tide[...]` |
| 结构化并发：`hive { ... }` |
| 类型与精化契约：类型 + 精化契约 `where` |
| 函数组合、管道、模块组合 |
| 模式匹配、光学访问、不可变更新 |
| 持久化数据结构与结构共享 |
| 效应日志、确定性重放、时间旅行调试 |
| 卫生宏、编译期展开 |
| 可移植字节码与多后端运行时 |
| 包管理、能力清单、社区生态 |

## 2. 核心哲学

- **纯函数默认**：普通函数不能偷偷做 I/O、抛异常、开线程。
- **效应显式**：副作用写在类型里，如 `~ Tide[Console, Net]`。
- **类型即契约**：主类型系统是 HM + ADT + 行多态；可选精化契约表达前后条件。
- **不可变优先**：数据默认不可变，持久化共享；局部安全可变区可优化性能。
- **资源线性化**：文件、锁、连接等能力可线性检查，防止重复释放和悬空使用。
- **结构化并发**：并发任务必须活在 `hive` 生命周期内，异常自动取消兄弟任务。
- **可重放**：效应执行可记录为日志，测试与调试可确定性重放。

## 3. 语法速览

### 函数、泛型、管道

fn add(x: Int, y: Int) -> Int = x + y

fn id[a](x: a) -> a = x

let result =
  [1, 2, 3, 4]
  |> map(inc)
  |> filter(odd)
  |> fold(0, add)

### 代数数据类型与模式匹配

type Tree[a] =
  | Leaf
  | Node(Tree[a], a, Tree[a])

fn mapTree[a, b](t: Tree[a], f: a -> b) -> Tree[b] =
  match t {
    Leaf => Leaf
    Node(l, x, r) => Node(mapTree(l, f), f(x), mapTree(r, f))
  }

### 契约

contract sorted(xs: List[Int]) =
  match xs {
    [] => true
    [_] => true
    x :: y :: rest => x <= y && sorted(y :: rest)
  }

fn sort(xs: List[Int]) -> List[Int]
  where sorted(result)
= xs |> quicksort

## 4. 类型与效应系统

Loomi 的类型分三层：

1. **值类型**：`Int`、`String`、`List[a]`、`Tree[a]`、记录、变体。
2. **效应行**：`Tide[Console, Net, Fail[E] | r]`，可扩展、可消除、可多态。
3. **契约层**：`where` 前后条件，静态可证则消除，否则可转为运行断言。

例子：

effect Console {
  print: String -> Unit
}

fn greet(name: String) -> Unit ~ Tide[Console] =
  Console.print("你好，" ++ name)

fn main() -> Unit ~ Tide[IO] =
  handle greet("澜织") with {
    print(msg, k) => {
      IO.writeLine(msg)
      k(())
    }
  }

这里 `greet` 只知道 `Console`，`main` 用处理器把 `Console` 解释成 `IO`。  
效应由处理器解释为具体操作，纯函数区不直接执行这些操作。

## 5. 并发：结构化并发

fn fetchPair() -> (Page, Page) ~ Tide[Net, Async] =
  hive {
    let a = spawn fetch("https://a.example")
    let b = spawn fetch("https://b.example")
    (await a, await b)
  }

- `hive` 是结构化并发作用域。
- 子任务不会逃逸出 `hive`。
- 任一任务失败默认取消兄弟任务。
- `spawn` 返回 `Task[a, e]`，`await` 获取结果。
- 通道 `Chan[a]`、信号量、超时等都由效应库提供，不污染核心语义。

## 6. 不可变更新与光学

Loomi 提供轻量光学语法：

let user2 =
  user
  |> set(user.address.city, "杭州")
  |> over(user.tags, append("函数式"))

底层是普通数据结构与函数，光学只是可组合的库级抽象。

## 7. 模块、宏与包

module Math.Lattice {
  export fn meet[a](x: a, y: a) -> a = min(x, y)
  export fn join[a](x: a, y: a) -> a = max(x, y)
}

import Math.Lattice { meet, join }

宏是卫生的：

macro unless(cond, body) =
  quote { if !(splice(cond)) { splice(body) } }

包管理器叫 **Rainforest**，每个包声明能力清单：网络、文件、进程、时钟、随机数等，安装时可见。

## 8. 编译与运行时

- 前端：增量解析、HM 类型推导、效应行推导、契约检查。
- 中间层：带效应标记的 SSA。
- 后端：Loomi 字节码，以及 WASM / 原生后端。
- 运行时：M:N 轻量纤维、工作窃取调度、持久化数据结构、精确 GC 可选。
- 调试：效应日志支持确定性重放，可回看并发交错与外部输入。
- 优化：尾调用、内联、逃逸分析、局部可变区、结构共享、宏展开。

## 9. 综合示例

type Json =
  | JNull
  | JBool(Bool)
  | JNum(Float)
  | JStr(String)
  | JArr(List[Json])
  | JObj(Map[String, Json])

effect Console {
  print: String -> Unit
}

contract sorted(xs: List[Int]) =
  match xs {
    [] => true
    [_] => true
    x :: y :: rest => x <= y && sorted(y :: rest)
  }

fn sort(xs: List[Int]) -> List[Int]
  where sorted(result)
= xs |> quicksort

fn main() -> Unit ~ Tide[Console, IO] =
  handle Console.print("澜织已启动") with {
    print(msg, k) => {
      IO.writeLine(msg)
      k(())
    }
  }

一句话总结：**Loomi 用效应系统管理副作用，用结构化并发管理并发，用契约类型管理正确性，用组合式结构管理程序结构。**

---

## 回答 B

# 语言提案：Aster（星芒）

> 一句话：Aster 是一门**纯函数式、强类型、默认不可变、以能力效应和结构化并发为核心**的现代函数式编程语言。  
> 它不追求“又一个 Haskell”，而是强调三件事：**纯函数是默认、副作用在类型上可见、并发不靠共享内存**。

---

## 1. 设计目标

1. **纯函数优先**：默认不可变、无隐式全局状态、无 null。
2. **副作用显式但低噪音**：用代数效应和效应行表达 IO、随机、异常、并发；大部分效应可由编译器推断。
3. **数据与行为分离**：记录/变体用结构类型，行为用 trait，不支持类继承。
4. **结构化并发**：并发任务有明确生命周期，取消、异常、资源释放可组合。
5. **可预测性能**：严格求值为主，尾调用保证，持久化数据结构，可编译到原生和 WASM。
6. **优秀工具链**：格式化、LSP、REPL、包管理、测试、文档一体化。

---

## 2. 核心语法

### 2.1 函数与管道

```aster
fn add(x: Int, y: Int): Int = x + y

fn id<A>(x: A): A = x

fn compose<A, B, C>(f: B -> C, g: A -> B): A -> C =
  \x -> f(g(x))
```

Aster 支持管道写法：

```aster
fn doublePositive(xs: [Int]): [Int] =
  xs
    |> filter(\x -> x > 0)
    |> map(\x -> x * 2)
```

### 2.2 记录与变体

记录默认结构化、行多态；和类型是名义类型。

```aster
type User = {
  id: Int,
  name: String,
  active: Bool,
}

fn nameOf(p: { name: String, ...r }): String = p.name
```

```aster
type Result<A, E> = Ok(A) | Err(E)

fn findUser(id: Int, users: [User]): Result<User, String> =
  match users |> find(\u -> u.id == id) {
    Some(u) => Ok(u),
    None    => Err("user not found"),
  }
```

### 2.3 模式匹配

```aster
type Shape = Circle(Float) | Rect(Float, Float)

fn area(s: Shape): Float =
  match s {
    Circle(r) => 3.14159 * r * r,
    Rect(w, h) => w * h,
  }
```

Aster 要求穷尽性检查，未覆盖分支是编译错误。

---

## 3. 类型系统与效应系统

### 3.1 函数类型

普通函数：

```aster
Int -> String
```

带效应的函数：

```aster
A -> B !E
```

其中 `E` 是效应行，例如：

```aster
fn readName(): String !{Console, IO} = ...
```

纯函数不写效应：

```aster
fn inc(x: Int): Int = x + 1
```

等价于效应为空。

### 3.2 效应行多态

```aster
fn twice<A>(x: A, f: A -> A !e): A !e =
  f(f(x))
```

编译器推断最小效应集合；公共 API 建议显式标注。

效应行可以组合、别名化：

```aster
type App = !{Console, Random, IO}

fn run(): Unit !App = ...
```

### 3.3 Trait 与实现

```aster
trait Show<A> {
  show: A -> String
}

impl Show<Int> {
  fn show(x: Int): String = Int.to_string(x)
}

impl<A> Show<[A]> where Show<A> {
  fn show(xs: [A]): String =
    "[" + (xs |> map(Show.show) |> String.join(", ")) + "]"
}
```

Aster 使用 trait 做 ad-hoc 多态，不使用继承。

### 3.4 默认严格求值

Aster 默认 call-by-value，保证求值顺序可预测。惰性值需显式使用 `Lazy<T>`：

```aster
let x: Lazy<Int> = lazy { expensiveComputation() }
let y = force(x)
```

不强制所有函数停机；对关键代码可使用：

```aster
total fn normalize(x: Expr): Expr = ...
```

`total` 会触发终止性检查。

---

## 4. 能力效应：Aster 的核心特色

Aster 把副作用建模为**能力**。函数只能调用它声明拥有或由上下文提供的能力。

```aster
effect Console {
  print: String -> Unit,
  read: () -> String,
}

effect Random {
  int: (Int, Int) -> Int,
}
```

使用能力：

```aster
fn askName(): String !Console =
  Console.print("What is your name?")
  Console.read()
```

处理效应：

```aster
fn main(): Unit !IO =
  handle askName() with Console {
    print(s) => {
      hostPrint(s);
      resume(())
    },
    read() => resume("Ada"),
  }
```

要点：

- `resume` 默认 one-shot；需要多 shot 时显式标记 `multi`。
- `IO` 是运行时在 `main` 入口授予的底层能力。
- 测试中可用 handler 模拟 `Console`、`Random`、`Time`、`Http`。
- 没有隐式环境权限：库函数不能偷偷执行 IO，除非类型声明了相应效应。

---

## 5. 结构化并发

Aster 不鼓励共享可变状态，并发通过 effect、任务和通道实现。

```aster
fn fetchBoth(): (Data, Data) !{Async, Http} =
  scope {
    let a = spawn(fetch("https://a.example"))
    let b = spawn(fetch("https://b.example"))
    (await(a), await(b))
  }
```

规则：

- `scope` 内创建的任务必须在 scope 结束前完成或被取消。
- 任一子任务失败时，scope 自动取消其余任务。
- 通道类型：`Chan<T>`，只允许消息传递。
- 调度器是 effect handler，因此测试可替换为确定性调度器。

---

## 6. 模块与包

```aster
mod geometry {
  pub type Point = { x: Float, y: Float }

  pub fn norm(p: Point): Float =
    Float.sqrt(p.x * p.x + p.y * p.y)
}

use geometry::{Point, norm}
```

包配置 `aster.toml`：

```toml
[package]
name = "my-app"
version = "0.1.0"
edition = "2026"

[dependencies]
aster-json = "1.2"
```

模块规则：

- `pub` 显式导出。
- trait 实现遵循 orphan rule。
- 包级别语义版本。
- 文档注释 `///` 自动生成文档。

---

## 7. 语义与实现策略

### 7.1 求值语义

- 默认严格求值、左到右求值。
- 不可变值；持久化列表、映射、集合。
- 尾调用在尾位置保证优化。
- 模式匹配穷尽性检查。
- 无 null，使用 `Option<T>`；错误使用 `Result<T, E>` 或效应。

### 7.2 核心演算

内部核心可定义为带行多态的 System F 扩展：

```text
类型：
  A, B ::= Int | Bool | String | A -> B !E
         | [A] | (A, B) | {l: A, ...}
         | A | B | μX. A

效应：
  E ::= {} | {op | E} | e | E ∪ E

表达式：
  e ::= x | lit | λx. e | e e
      | let x = e in e
      | match e { ... }
      | handle e with h
```

类型判断概要：

```text
Γ ⊢ f : A -> B !E    Γ ⊢ x : A
--------------------------------
Γ ⊢ f(x) : B !E
```

处理效应时，handler 从效应行中移除对应操作。

### 7.3 编译目标

- 原生：LLVM 或 Cranelift。
- Web：WASM。
- 解释器：用于 REPL 和教学。
- 运行时：带循环回收的 tracing GC；可选引用计数优化。
- 效应实现：CPS/defunctionalized handler，针对常见效应做直接优化。

---

## 8. 工具链

计划提供：

```bash
aster new my-app
aster run
aster test
aster fmt
aster doc
aster repl
```

编辑器支持：

- LSP：补全、跳转、类型提示、效应提示、诊断。
- 格式化器：唯一官方风格。
- 测试框架：内建 property testing。
- 文档生成器：从类型签名和 doc comment 生成。

---

## 9. 完整示例

```aster
type User = {
  id: Int,
  name: String,
  active: Bool,
}

fn activeNames(users: [User]): [String] =
  users
    |> filter(\u -> u.active)
    |> map(\u -> u.name)
    |> sort

effect Console {
  print: String -> Unit,
}

fn report(users: [User]): Unit !Console =
  let names = activeNames(users)
  Console.print("Active users: " + String.join(", ", names))

fn main(): Unit !IO =
  handle report([
    { id: 1, name: "Ada", active: true },
    { id: 2, name: "Lin", active: false },
    { id: 3, name: "Grace", active: true },
  ]) with Console {
    print(s) => {
      hostPrint(s);
      resume(())
    }
  }
```

输出：

```text
Active users: Ada, Grace
```

---

## 10. MVP 范围

第一版建议只实现：

1. 函数、let、管道、模式匹配。
2. Int/Bool/String/Unit、列表、元组、记录、和类型。
3. HM 类型推断 + 显式泛型 + trait。
4. 代数效应与 handler。
5. 模块和基础包管理。
6. 解释器 + WASM 后端。
7. 格式化器、REPL、基础 LSP。

暂缓：依赖类型、宏系统、多 shot handler 优化、线性类型、JIT。

---

**总结**：Aster 的“新”不在于发明孤立的语法糖，而在于组合出一套统一模型：  
**纯函数 + 结构数据 + trait 多态 + 能力效应 + 结构化并发 + 可预测运行时**。  
它适合写应用、服务端、工具链和 WASM 前端逻辑，同时保持函数式语言的可组合性与类型安全。

---

## 评审输出

{"A": {"logic": 9, "concreteness": 8, "actionability": 8, "originality": 9, "overall": 8}, "B": {"logic": 9, "concreteness": 9, "actionability": 9, "originality": 8, "overall": 9}, "winner": "B", "reason": "B 在细节完整性与可操作性上更突出，提供了核心演算形式化、明确的 MVP 范围、工具链命令和可运行的完整示例；A 在原创概念上略胜，但部分特性如契约验证和可重放调试未充分展开，整体略逊。"}
