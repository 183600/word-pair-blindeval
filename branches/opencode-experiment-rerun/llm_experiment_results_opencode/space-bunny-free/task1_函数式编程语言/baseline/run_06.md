# [rerun:space-bunny-free] 任务1 函数式编程语言 | 条件: baseline | 第 6 次

**Prompt:** 设计一个全新的函数式编程语言

**耗时:** 37.9s | **tokens:** 196/6438(推理 2176) | **finish:** stop

---

# Loom（织语）— 一门面向并行与显式副作用的函数式编程语言

> 设计文档 v1.0 · 一句话定位：**"纯函数自动并行，副作用写进类型，资源由类型系统保证释放。"**

---

## 一、设计目标与取舍

大多数现代函数式语言（Scala、Koka、Futhark、Idris）在"纯净性"上妥协（glob mutable、null、隐藏 IO），而系统语言（Rust、Swift）在"可组合性"上妥协。我的目标是同时拿两边的甜头：

| 目标 | 手段 |
|---|---|
| 一切可组合，无隐藏状态 | 不可变数据 + 纯函数默认 |
| 副作用不可隐藏 | 效应**标注在类型里**（effect rows） |
| 资源不泄漏 | 线性类型（linear types）可选强制 |
| 纯函数自动并行 | 编译器识别纯调用点 + 工作窃取运行时 |
| 零运行时开销的抽象 | 类型类特化 + 编译期擦除 |
| 错误友好 | 穷尽性检查 + "你想匹配的是……"式诊断 |

明确放弃的东西：null（用 `Option`）、可变全局、动态 duck typing、隐式数值转换、运算符重载的运行时字典。

---

## 二、基本语法

```loom
//换行敏感，无需分号
module geometry

type Shape =
  | Circle(radius: Float)
  | Rect(width: Float, height: Float)
  | Triangle(a: Float, b: Float, c: Float)

fn area(s: Shape) -> Float =
  match s {
    Circle(r)                    => PI * r * r
    Rect(w, h)                   => w * h
    Triangle(a, b, c) when a+b>c => heron(a, b, c)
    _                            => 0.0
  }

fn main() -> !IO Unit =
  let shapes = [Circle(1.0), Rect(2.0, 3.0), Triangle(3.0, 4.0, 5.0)]
  let total  = shapes |> map(area) |> sum
  println("total area = {total}") // 花括号插值
```

要点：

- `fn` 声明**统一柯里化**：`f a b` = `f a b`，无 tuple 参数。
- 块是表达式，最后一行即值。
- `|>` 管道在编译期展开为嵌套调用，并做**融合优化**（`map |> sum` 不产生中间列表）。
- 类型标注可选，由 HM 推断补全；`.loom` 文件里建议写全（像 Rust 那样为读者和编译器服务）。
- 标识符支持 unicode；关键字仅 12 个（`fn let match type mod interface use where as if else derive`）。

---

## 三、类型系统

### 3.1 代数数据类型 + 构造器解析

类型构造器与值构造器**共享命名空间**，靠首字母大小写区分（`Circle` 是构造器，`circle` 是普通函数）：

```loom
type Maybe[a] = Nothing | Just(a)
type Result[a, e] = Ok(a) | Err(e)     // 编译器内建，支持 `?`

fn first(xs: [a]) -> Result[a, Unit] =
  match xs {
    []       => Err(Empty)
    [x, .._] => Ok(x)
  }
```

### 3.2 记录 + 行多态（Row Polymorphism）

这是 Loom 的"开放结构"，让"只关心一部分字段"的函数可以复用而不必定义一堆包装类型：

```loom
fn label(r: {name: String | r}) -> String = r.name     // r: 其余任意字段（开放）
fn make(name: String, age: Int) -> {name: String, age: Int} =
  {name: name, age: age}
```

行变量 `| r` 可出现在类型参数、返回值、参数位置；推断时通过**行统一（row unification）**完成，复杂度与"每字段一次子目标"同阶，实践上很快。

### 3.3 接口（类型类）+ 特化

```loom
interface Eq a where
  eq(a, a) -> Bool

interface Container f where
  empty() -> (f a, a)
  extend(f a, a) -> f a

derive(Eq, Show) for Shape // derive 自动生成实例

// 实例即编译期特化，零字典开销
instance Eq a => Eq [a] where
  eq(xs, ys) = len(xs) == len(ys) && all(zip_with(xs, ys, eq))
```

约束传播支持重载解析（`show1`走 `Int` 实例，`show (1, "a")` 走 tuple 实例），**不做自动数值扩展**：`1 + 1.0` 报错并建议 `1.0 + 1.0`。

---

## 四、模式匹配（语言的核心特性）

### 4.1 穷尽性检查```loom
fn to_string(s: Shape) -> String =
  match s {
    Circle(r)      => "circle"
    Rect(w, h)     => "rect"
  }
// error[non-exhaustive]: 无法覆盖 Shape
//   ┌ 4:4
//   │ missing: Triangle(Float, Float, Float)
//   │ help: 添加 `Triangle(a, b, c) => ...`，或 `_ => panic("unreachable")`
//   note: 编译器已证明该分支不可达，故 panic 分支不产生代码
```

### 4.2 `as` 视图模式（view patterns）

把"匹配某种形状/性质"与"解构"分离，可读性大幅提升：

```loom
fn classify(cfg: Record) -> String =
  match cfg {
    as [a, b, ..rest] if a > b  => "descending"
    as {mode: "fast", ..}       => "turbo"
    as Map(k, _) if k.is_upper => "flagged"
    as Int(n) when n % 2 == 0   => "even"
    _                           => "other"
  }
```

`as P` 是"浅匹配视图"，失败则继续下一分支，不消耗值的所有权语义。

### 4.3 嵌套/位置/字面量

```loom
match point {
  {x: 0, y: 0}            => "origin"
  {x: x, y: y} @ origin   => "somewhere"        // @绑定整值
  {x, y}                  => "at {x},{y}"       // 字段省略名
}
```

---

## 五、效应系统：让副作用签名可见

Loom 的函数类型携带一个**效应行**：

```
expr :  τ  !e // 有副作用 e 的 τ 值
```

```loom
fn read_file(p: Path) -> !IO Bytes              // 纯函数，隐式 !pure
fn push(xs: [Int], v: Int) -> !State [Int]      // 状态效应
fn parse(s: String) -> !ParseErr String          // 无失败（ParseErr 是类型，不是效应）
fn fetch(url: Url) -> !{IO, Net} Bytes          // 复合效应行
```

### 5.1 `let!` 绑定 + 局部处理（effect handlers）

```loom
fn load(path: Path) -> !IO Config =
  let! raw = io.read(path)
  let! conf  =
    use {ParseErr} {                 // 局部效应处理器：把 Err 变成警告 + 默认值
      match parse(raw) {
        Ok(c)  => Ok(c)
        Err(e) => do io.warn("bad config: {e}"), Ok(Config::default())
      }
    }
  io.write(cache_dir, serialize(conf))
```

`use {E} { ... }` 是**词法作用域的效应处理器**，编译器把它编译成 CPS 变换（one-pass 的 continuation 复制 + 尾调用优化），无运行时 handler 表开销。

### 5.2 `?` 运算符

```loom
fn main() -> !IO Unit =
  let args = env::args()?
  let cfg    = Config::load(args[0])?
  let report = Report::new(cfg)?
  report.emit()
```

### 5.3 效应多态

```loom
fn twice(f: () -> !e a) -> !e a = let x = f(); f()
fn run_guarded() -> !{IO, Net} Unit =
  use {Net} {                                    // 抑制 Net：断网返回默认
    let body = fetch_or_empty(url)
    io.print(body)
  }
```

> **设计决策**：不支持 `unsafe`、不支持效应类型转换（`unIO`）、不支持全局 handler。这让"这个函数会不会发网络请求"永远可静态判定——这是可审计性的关键。

---

## 六、线性类型：资源由类型保证

```loom
linear File = linear { _fd: Fd, _path: Path }

fn process(path: Path) -> !IO Unit =
  let h = File::open(path)          // 线性值：必须在作用域末尾被消耗一次
  let data = h.read_all()
  analyze(data, path) // 把 h 借出去（borrow，编译期检查无重叠借用）
  // h 未被 close → error[linear-use]: File 在此函数结束时仍存活
  // help: 添加 `h.close()`，或 `let _ = h`（显式丢弃需写 `drop(h)`）
```

规则（简化版）：

- 线性值**恰好消耗一次**；`drop` 显式丢弃，`move` 显式转移。
- 可变借用 `&mut T` 排他；不可变借用 `&T` 可共享，二者不能重叠存活。
- 与 `!IO` 组合：跨 await点的借用被禁止（类似 Rust 的 Send 检查）。
- 线性函数值（闭包捕获线性变量时自动升格）可用于 RAII：`let _guard = Lock::acquire(m)`。

---

## 七、并行与惰性

纯函数是 Loom 的并行货币。

```loom
fn total_workload(items: [Item]) -> Int =
  par_map(items, fn it => expensive(it)) |> sum      // 显式并行（可被编译器自动识别）
```

**自动并行（v1 计划）**：编译器在 `fn` 调用点做副作用检查，若被调用函数及其间接调用图全为 `!pure`，且参数是"只读数据"（无 `&mut`、无线性捕获、无身份敏感操作如指针比较/哈希地址），则自动加入并行化候选。运行时通过**记忆化 thunk**（hash-consing by value）避免重复计算：

```loom
let k = key(user_input)                  // 纯函数：自动并行 + 结果缓存
let v = pmap(1..10_000, compute)          // 并行向量化执行（SIMD + 线程）
```

异步不是另一套语法，而是内建关键字：

```loom
let! a = http.get(url_a)                  // 阻塞等待，但挂起的是 fiber 而非线程
let! b = http.get(url_b)                 // 实际并发
combine(a, b)
```

每个任务运行在轻量 **fiber**（64KB 栈，栈可增长/收缩），工作窃取调度器（N 个 worker，无全局锁）。所以"同步代码看起来"就是异步的。

---

## 八、模块与包

```loom
mod parser {
  pub type Token = Int | Ident(String) | Op(String)
  pub fn tokenize(src: String) -> Result<[Token], LexError>
  private fn scan_char(c: Char) -> bool
}

use parser::{Token, tokenize}          // 具名导入
use parser as p // 别名
use prelude::*                         // 预导入：Option/Result/List/String 接口
```

- 无循环依赖（模块图由 `import` 边构建，编译期检测）。
- 包 = Git 仓库 / 目录，`loom.toml` 声明；包管理器命令 `loom add parser`。
- 版本：`^1.2`，语义化版本 + 编译期 ABI 兼容性检查。

---

## 九、内存模型与运行时

- **堆**：不可变数据，不可移动的并发标记-清除 GC（pause-free / 分代不清扫代际）。
- **栈**：值优先就地表示，小对象 ≤24B 内联；`Option<Int>` 是 `niche` 优化，无额外分配。
- **无 `Rc<RefCell<T>>` 式内部可变性**。需要内部可变时，用显式 effect：
  ```loom
  fn bump(c: Counter) -> !State Int = c.n := c.n + 1
  ```
好处：可推断的别名关系 → 并行化不会因"看起来纯"而出错。
- **FFI**：`extern "C" fn` 声明，边界处强制 `linear` + `unsafe`，FFI 类型不可跨 FFI 携带效应。
- 运行时库 `loomrt` 提供 fiber、并发 GC、io_uring事件循环、调度器；约 15k 行 Rust。

---

## 十、编译器实现

```
源码 → Lexer/Parser (rowan, 错误容忍)
     → AST →名字解析/重载解析(实例查找)
     → HM 类型推断 + 行多态 + 效应推断（约束统一化，Rémy-style）
     → 模式匹配编译（决策树 + 移位矩阵，支持列压缩）
     → MIR：SSA + 效应/线性/借用检查（借用检查置于 MIR 层，诊断更准）
     → 优化：闭联/无分配 lambda 提升、管道融合、向量化、TCO(trampoline)、
             效应 handler 的 one-pass CPS 变换
     → 后端：Cranelift → LLVM（12+平台） / WasmGC（浏览器·边缘）
     → 运行时：fiber 调度器 + io_uring + 并发 GC
```

性能目标（v1）：热路径可达 C 的 80–90%；闭包分配在逃逸分析可判定时为 0；`map |> sum` 与手写循环同汇编。

**工具链**：`loomc`、`loom fmt`（格式化器）、`loom repl`（带类型标注的交互式）、`loom test`（属性测试 + effect 快照测试）、`loom lint`、`loom doc`、官方 LSP + VS Code/Neovim 插件（内联类型、补全、重构、重命名）、`cargo`-风格发布流程。

---

## 十一、完整示例：一个小型配置语言求值器

```loom
type Value = Num(Float) | Str(String) | List([Value]) | Bool(Bool)
type Expr  = Lit(Value) | Var(String) | Add(Expr, Expr) | If(Expr, Expr, Expr)

fn eval(e: Expr, env: {| String |}) -> Result<Value, EvalErr> =
  match e {
    Lit(v)        => Ok(v)
    Var(n)        => env.lookup(n)?
    Add(a, b)     => num(eval(a, env)?) + num(eval(b, env)?)
    If(c, t, f)   => match eval(c, env)? {
                     Bool(true) => eval(t, env)?
                     _          => eval(f, env)?
                   }
  }

fn run(src: String) -> !IO Unit =
  let! ast  = parse_expr(src)?
  let  env  = { "pi" => Lit(Num(3.14159)) }
  let  out  = eval(ast, env)?
  io.println(show(out))
```

无异常、无 null、无全局变量；`env.lookup` 的失败路径在类型里是 `Result`，`?` 让它只写一次。

---

## 十二、与现有语言的差异点

| 维度 | ML 系(Haskell/OCaml) | Rust/Swift | **Loom** |
|---|---|---|---|
| 副作用 | monad，隐藏于类型构造 | 无类型追踪 | **效应行，写在签名里** |
| 纯函数并行 | 需用户标注 / GHC 自动并行 | 手动 Send+Sync 标注 | **编译器自动判定 + 值缓存** |
| 资源管理 | GC（不精确） | 所有权（全强制） | GC 默认，**linear 可选**，可混用 |
| 异步 | 需协程库 | async/await + 状态机 | **内建 fiber，同步语法即并发** |
| 记录扩展 | 依赖 typeclass/包装类型 | 结构体固定 | **行多态，开放记录** |
| 空安全 | option（需解包） | Option（强制） | Option + **穷尽匹配强制** |
| 运行时开销 | 装箱/字典 | 零 | **零（特化 + 擦除）** |

真正的"新"在于把**线性类型、效应系统、开放记录、自动并行**四件通常互斥的东西塞进同一个可推断的 HM 框架，并让每个的诊断都能落到具体源码位置。

---

## 十三、风险与已知取舍（诚实版）

1. **效应推断的编译时**：全程序效应推断 + 行统一可能导致超线性复杂度 → 折中方案是**局部推断 + 边界显式标注**（像 Rust 的 `-> !IO`），默认在模块签名处要求写全。
2. **线性类型的可用性**：借用检查放在 MIR 层，诊断质量能否达到 Rust 水平取决于工程投入；v0.2 前可能只支持"移动/消耗"这三种简单规则，不做 `&mut` 别名分析。
3. **自动并行的确定性**：程序必须可复现 → 禁止以指针身份或浮点归约顺序作为语义，浮点并行归约需显式 `ordered_sum`。
4. **生态**：从零开始造标准库、包管理、文档、编辑器支持是最难的部分，因此 v0.1 目标只有语言核心 + 300 个函数的 `std`。
5. **学习曲线**：同时有 4 个类型系统维度 → 官方教程设计成"渐进四阶段"（表达式 → 模式匹配 → 效应 → 线性），每阶段可独立交付价值。

---

## 十四、路线图

| 版本 | 内容 |目标 |
|---|---|---|
| v0.1 (6 mo) | ADT、记录、模式匹配、HM 推断、LLVM 后端、`std` 300 函数 | 能编译 FizzBuzz 到 JSON 到玩具解释器 |
| v0.2 (4 mo) | 效应行 + handlers、`?`、`use{}` | 写出真实的 CLI工具（如本语言自己的构建脚本） |
| v0.3 (3 mo) | 线性类型 + 借用检查、fiber、io_uring | 能写 FFI 与网络服务 |
| v0.4 (3 mo) | 自动并行、thunk 记忆化、WasmGC 后端 | 数值与解析类负载接近 C |
| v1.0 | 稳定性保证、形式化规范、包注册表 | 生态开放 |

---

## 十五、一句话总结

**Loom 让"我写的是纯函数"成为编译器可验证、运行时可利用的契约**：副作用被签名诚实记录，资源被类型承诺释放，纯函数被自动并行——而所有这些都不需要在源码里多写一个 `unsafe`、一个 `mut` 或一个 `thread::spawn`。

如果你想，我可以继续展开其中任一块：**完整的 EBNF 文法**、**效应推断算法与 CPS 变换的伪代码**、**借用检查的规则集与诊断示例**，或者**把 Loom 解释器用 Python 实现出来跑通上面的配置语言求值器**。
