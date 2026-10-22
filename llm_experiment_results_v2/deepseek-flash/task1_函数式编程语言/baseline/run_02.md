# [v2:deepseek-flash] 任务1 函数式编程语言 | 条件: baseline | 第 2 次

**Prompt:** 设计一个全新的函数式编程语言

**耗时:** 39.92s | tokens: 37/7660

---

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
