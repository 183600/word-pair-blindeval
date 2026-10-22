# [v2:deepseek-flash] 任务1 函数式编程语言 | 条件: baseline | 第 10 次

**Prompt:** 设计一个全新的函数式编程语言

**耗时:** 34.8s | tokens: 37/6627

---

下面给出一个可落地的全新函数式语言设计方案。

---

# 语言名：澜（Lan）

**定位**：纯函数为默认、效果显式、强类型、结构化并发、面向实用工具链的通用函数式编程语言。  
**文件扩展名**：`.lan`  
**核心口号**：*默认纯净，效果显式，错误可追踪，并发有边界。*

---

## 1. 设计目标

1. **纯函数默认**：普通函数没有副作用；IO、随机、时间、异常、并发等通过效果类型显式标注。
2. **静态强类型但可推断**：Hindley–Milner 风格类型推断 + 双向类型检查；签名可选但推荐。
3. **模式匹配与代数数据类型优先**：ADT、穷尽性检查、嵌套模式、记录行多态。
4. **效果系统实用化**：代数效果 + 处理器；支持效果多态与行多态。
5. **并发安全**：结构化并发，任务生命周期有作用域，取消自动传播。
6. **性能可预测**：严格求值，尾调用优化；惰性求值需显式使用 `Lazy[a]`。
7. **工具链完整**：格式化、包管理、REPL、LSP、测试框架、文档生成。

第一版刻意不加入依赖类型、宏系统、隐式搜索等高风险特性，保证语言可实现、可学习、可调试。

---

## 2. 基础语法

### 2.1 函数与表达式

```lan
module Main

import std.io { println }

fn inc(x: Int) -> Int = x + 1

fn add(x: Int, y: Int) -> Int = x + y

fn main() -> Unit ! {io} =
  let n = inc(41)
  println("answer = ${n + 1}")
```

所有结构都是表达式，没有传统语句。`! {io}` 表示函数可能执行 IO 效果；纯函数可省略效果标注。

---

### 2.2 代数数据类型与模式匹配

```lan
type Shape =
  | Circle(Float)
  | Rect(Float, Float)

fn area(shape: Shape) -> Float =
  match shape {
    Circle(r) => 3.14159 * r * r
    Rect(w, h) => w * h
  }
```

模式匹配要求穷尽；缺失分支是编译错误，而不是运行时异常。

---

### 2.3 记录与行多态

```lan
type User = { name: String, age: Int, ..r }

fn name_of(u: { name: String, ..r }) -> String =
  u.name
```

`..r` 表示剩余字段行，函数可接受任何至少包含 `name: String` 的记录。

---

### 2.4 Trait / 类型类

```lan
trait Show[a] {
  fn show(x: a) -> String
}

impl Show[Int] {
  fn show(x: Int) -> String = Int.to_string(x)
}

fn print_all[a: Show](xs: List[a]) -> String =
  xs |> List.map(Show.show) |> String.join(", ")
```

---

## 3. 类型系统

澜采用：

- 双向类型检查；
- 局部 HM 类型推断；
- rank-1 多态；
- 行多态记录；
- 有限高阶类型（HKT）支持；
- Trait 约束与实例解析；
- 穷尽性检查；
- 无非空陷阱：没有 `null`，使用 `Option[a]`。

示例：

```lan
type Option[a] = None | Some(a)
type Result[a, e] = Ok(a) | Err(e)
```

错误处理既可返回 `Result`，也可通过 `Fail[e]` 效果传播：

```lan
fn parse_int(s: String) -> Int ! {fail[ParseError]} =
  ...
```

---

## 4. 效果系统

澜的核心特点是：**副作用是类型的一部分**。

效果类型写成：

```lan
fn read_file(path: Path) -> String ! {io}
fn rand() -> Float ! {random}
fn fetch(url: Url) -> Page ! {io, async, fail[HttpError]}
```

纯函数等价于空效果：

```lan
fn pure_add(x: Int, y: Int) -> Int = x + y
```

效果支持多态：

```lan
fn map[a, b, e](f: a -> b ! e, xs: List[a]) -> List[b] ! e =
  match xs {
    Nil => Nil
    Cons(x, rest) => Cons(f(x), map(f, rest))
  }
```

### 4.1 效果声明

```lan
effect Log {
  op log: String -> Unit
}
```

### 4.2 使用效果

```lan
fn greet(name: String) -> Unit ! Log =
  Log.log("hello ${name}")
```

### 4.3 处理器

```lan
fn main() -> Unit ! {io} =
  handle greet("Lan") with {
    Log.log(msg, k) => {
      println(msg)
      k(())
    }
  }
```

`k` 是续延。默认采用一次性续延以优化性能；需要多次续延时显式标注 `multi`。

---

## 5. 模块与包管理

```lan
module App.Main

import std.io { println }
import std.list as List
import MyProject.Config { Config }

pub fn run(config: Config) -> Unit ! {io} =
  println(config.name)
```

包描述文件 `lan.toml`：

```toml
name = "my-app"
version = "0.1.0"

[dependencies]
json = "1.2"
http = "0.8"
```

工具链命令：

```bash
lan new my-app
lan run
lan test
lan fmt
lan repl
lan doc
```

---

## 6. 并发模型

并发通过 `Async` 效果表达，并采用结构化并发：

```lan
fn fetch_all(urls: List[Url]) -> List[Page] ! {io, async} =
  scope {
    urls
    |> List.map(fn u -> spawn fetch(u))
    |> Task.join_all
  }
```

规则：

- `spawn` 创建的任务必须属于某个 `scope`；
- 离开 `scope` 前自动等待或取消子任务；
- 任一子任务失败时，兄弟任务自动取消；
- 取消通过效果传播，不使用不可控异常；
- 调度器可替换：单线程确定性调度、多线程工作窃取、浏览器事件循环。

---

## 7. 求值与运行时

- 默认严格求值；
- 可选惰性：`Lazy[a]`、`lazy expr`、`force x`；
- 不可变值 + 结构共享；
- 尾调用优化；
- 追踪式 GC，分代并发回收；
- 资源安全通过作用域与 `Resource` 抽象处理；
- 编译路径：
  1. 解析 → 类型检查 → 效果检查；
  2. 降级到显式类型的核心 IR；
  3. 效果处理通过证据传递与选择性 CPS 实现；
  4. 后端支持 LLVM 原生代码与 WebAssembly。

---

## 8. 一个完整示例

```lan
module Main

import std.io { println }
import std.file { Path, read_file }
import std.string { split_whitespace }
import std.list { length }

fn word_count(path: Path) -> Int ! {io} =
  let text = read_file(path)
  text
  |> split_whitespace
  |> length

fn main() -> Unit ! {io} =
  let n = word_count(Path("input.txt"))
  println("words = ${n}")
```

如果加入错误处理，可写成：

```lan
fn safe_word_count(path: Path) -> Int ! {io, fail[IoError]} =
  let text = read_file(path)?
  text |> split_whitespace |> length
```

其中 `?` 表示将 `Fail` 效果继续向上传播。

---

## 9. 设计取舍

| 选择 | 理由 |
|---|---|
| 严格求值 | 性能与调试更可预测；惰性显式化 |
| 效果显式 | 比隐式异常/全局状态更安全，比全 monad 更易读 |
| 结构化并发 | 避免任务泄漏，取消语义清晰 |
| Trait 而非复杂模块函子 | 降低学习成本，保证工具链可用 |
| 第一版不做依赖类型 | 控制复杂度，先形成可用生态 |

---

**总结**：澜（Lan）是一门以“纯函数 + 显式效果 + 结构化并发”为核心的函数式语言。它保留 ADT、模式匹配、类型推断、Trait、行多态等函数式基础，同时用效果系统统一描述 IO、错误、状态与并发，目标是成为一门既可形式化思考、又能工程落地的通用语言。
