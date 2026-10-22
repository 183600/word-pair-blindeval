# [v2:deepseek-flash] 任务1 函数式编程语言 | 条件: baseline | 第 6 次

**Prompt:** 设计一个全新的函数式编程语言

**耗时:** 41.96s | tokens: 37/7860

---

# Lyre（琴语）v0.1 设计草案

我设计一门新的函数式编程语言 **Lyre（琴语）**。  
定位：**纯函数为默认、效应显式可追踪、类型系统实用、语法紧凑可工具化**。  
它不是要替代 Haskell/OCaml，而是尝试把 **代数效应 + 行多态 + 结构化记录 + 显式能力** 组合成一门更工程化的函数式语言。

---

## 1. 设计原则

1. **纯度默认**
   - 值不可变，函数默认无副作用。
   - IO、随机数、状态、异常、并发等全部建模为效应。

2. **效应显式且可组合**
   - 函数类型带效应行：`A -> B / E`
   - 使用 `handle` 解释效应，不依赖 Monad Transformer。
   - `main` 由运行时提供 `IO` 能力。

3. **严格求值 + 显式惰性**
   - 默认 call-by-value，行为可预测。
   - 需要惰性时使用 `lazy` / `force`。

4. **结构记录 + 名义 ADT**
   - 记录是结构化的，支持行多态。
   - 变体/ADT 是名义的，便于模块化和穷尽性检查。

5. **小核心、强工具**
   - 核心语言只有 λ、构造子、匹配、记录、效应 handler。
   - 官方提供格式化器、LSP、包管理器、REPL、WASM/LLVM 后端。

---

## 2. 基础语法

### 模块与函数

```lyre
module Main
use Std.IO

def fact(n: Int): Int =
  if n <= 0 then 1 else n * fact(n - 1)

def main(): Unit / IO =
  let name = IO.readLine("name? ")
  IO.println("Hello, {name}")
```

- `def` 定义函数。
- `/ IO` 表示该函数有 `IO` 效应。
- 纯函数不写效应，即效应行为空 `{}`。

### 代数数据类型与模式匹配

```lyre
type List<A> = Nil | Cons(A, List<A>)

def map<A, B>(xs: List<A>, f: A -> B): List<B> =
  match xs {
    Nil -> Nil
    Cons(x, rest) -> Cons(f(x), map(rest, f))
  }
```

编译器强制检查模式匹配穷尽性。

### 结构化记录与行多态

```lyre
type User = { name: String, age: Int }

def birthday(u: User): User =
  { ...u, age = u.age + 1 }

def getName(r: { name: String, ... }): String =
  r.name
```

`{ name: String, ... }` 表示至少包含 `name` 字段的开放记录类型。

### Trait 与实现

```lyre
trait Show<A> {
  def show(a: A): String
}

impl Show<Int> {
  def show(n: Int): String = intToString(n)
}
```

Trait 解析要求全局一致；重叠实例默认报错，可通过显式 newtype 消歧。

---

## 3. 效应系统

Lyre 的核心特色是 **效应行** 与 **handler**。

### 效应声明

```lyre
effect Ask {
  ask(): String
}

effect Console {
  print(String): Unit
  readLine(): String
}
```

### 带效应的函数

```lyre
def greet(): String / Ask =
  "Hello, " ++ ask()
```

函数类型：

```text
A -> B / E
```

其中 `E` 是效应行，例如：

```text
{}              -- 纯函数
{IO}            -- IO 效应
{Ask, IO}       -- 多个效应
{Ask | e}       -- 开放效应行
```

### Handler

```lyre
def runAsk<A>(answer: String, action: Unit -> A / Ask): A =
  handle action() with {
    return x -> x
    ask(resume) -> resume(answer)
  }
```

使用：

```lyre
def main(): Unit / IO =
  let msg = runAsk("Ada", fun() -> greet())
  IO.println(msg)
```

`handle` 消去指定效应，剩余效应继续向上传播。类型规则大致为：

```text
Γ ⊢ e : A / (E ∪ R)
Γ ⊢ handler : Handler(E, A, B)
--------------------------------
Γ ⊢ handle e with handler : B / R
```

---

## 4. 类型系统

Lyre 的类型系统以实用为主：

- Hindley–Milner 类型推断 + 双向检查。
- 支持参数多态：`List<A>`。
- 支持高阶类型，但默认不引入完整依赖类型。
- 记录使用行多态。
- 效应使用效应行推断与统一。
- ADT 名义化，记录结构化。
- 支持 trait / impl 约束。
- 模式匹配穷尽性检查。
- 无 `null`，错误使用 `Result<E, A>` 或 `Fail` 效应。

函数类型示例：

```lyre
map   : (List<A>, A -> B) -> List<B>
pure  : A -> B / {}
print : String -> Unit / Console
```

---

## 5. 求值与运行时语义

- 默认严格求值，参数从左到右求值。
- 值包括：字面量、闭包、构造子、记录、handler。
- 效应操作会挂起当前计算并捕获续延，由 handler 决定是否恢复。
- 支持 deep handler，即恢复后的计算仍在同一 handler 下运行。
- 尾调用保证优化：尾递归不会增长栈。
- 惰性通过 `lazy` 显式引入：

```lyre
lazy x = expensive()
...
force(x)
```

- 没有全局可变状态；状态通过 `State` 效应或显式传递实现。
- 运行时提供受控能力，如 `IO`、`FS`、`Env`、`Random`、`Async`。

---

## 6. 模块、包与 FFI

```lyre
module Data.List
use Std.{Option, Result}
```

- 模块是命名空间与导出集合。
- 包管理器名为 `lyre`，支持可复现构建与内容寻址依赖。
- FFI 必须标注效应：

```lyre
extern "c" def puts(s: String): Unit / IO
```

不安全的 FFI 需要显式 `unsafe` 块，并默认禁止在纯函数中调用。

---

## 7. 标准库雏形

- `Std.Core`：`Int`、`Float`、`Bool`、`Char`、`String`、`Unit`
- `Std.Data`：`List`、`Map`、`Set`、`Option`、`Result`
- `Std.IO`：文件、终端、环境变量
- `Std.Async`：结构化并发
- `Std.Test`：轻量测试框架
- `Std.Effect`：`State`、`Reader`、`Fail`、`Random` 等常用效应

---

## 8. 与现有语言的差异

| 特性 | Lyre 的选择 |
|---|---|
| 副作用 | 默认纯；效应行显式追踪 |
| 效应组合 | 代数效应 + handler，而非 Monad Transformer |
| 求值策略 | 严格求值，惰性显式 |
| 记录 | 结构化 + 行多态 |
| ADT | 名义化 + 穷尽性检查 |
| IO | 无环境隐式 IO，`main` 获得受控能力 |
| 工具链 | 格式化、LSP、包管理、WASM/LLVM 一等公民 |

---

## 9. MVP 实现路线

1. **解释器优先**
   - 用 Rust 或 OCaml 实现解析器、类型检查器、解释器。
2. **核心特性**
   - ADT、模式匹配、闭包、HM 类型推断、效应行、handler。
3. **工具链**
   - `lyre run`、`lyre fmt`、`lyre repl`、`lyre test`。
4. **后端**
   - 先输出 WASM，后续接 LLVM 或自研字节码。
5. **标准库**
   - 先覆盖 List、Option、Result、IO、State。

---

Lyre 的核心卖点可以概括为：

> **像 OCaml 一样可预测，像 Haskell 一样纯，用效应行和 handler 取代 Monad Transformer，并用结构化记录与行多态保持工程可组合性。**

如果你愿意，我可以继续给出 Lyre 的完整 EBNF 语法、类型规则，或一个最小解释器实现。
