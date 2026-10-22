# [v2:deepseek-v4-pro] 任务1 函数式编程语言 | 条件: baseline | 第 3 次

**Prompt:** 设计一个全新的函数式编程语言

**耗时:** 168.01s | tokens: 90/12021

---

# Aurora：一个全新函数式编程语言设计草案

> 语言名：**Aurora**  
> 核心理念：纯函数核心、显式效应、强静态类型、资源安全、并发友好。

---

## 1. 设计目标

- **默认纯函数**：默认表达式无副作用；副作用必须显式出现在类型中。
- **强静态类型**：拥有类型推断、行多态、效应行、线性类型。
- **效应系统**：用代数效应替代异常、全局可变状态等隐式副作用。
- **可预测性能**：默认严格求值，惰性求值需要显式声明。
- **资源安全**：文件句柄、网络连接等资源使用线性类型保证不泄漏、不使用已关闭资源。
- **现代并发**：轻量进程、通道、软件事务内存 STM。

---

## 2. 程序概览

一个 Aurora 程序通常是这样的：

```aurora
// hello.aur
fn main() -> () / {IO} = {
  println("Hello, Aurora!")
}
```

`/ {IO}` 表示该函数可能产生 IO 副作用。所有副作用都必须在类型中可见。

---

## 3. 核心语法

### 3.1 变量与函数

```aurora
let answer = 42

let add = fn(x: Int, y: Int) -> Int = x + y

// 语法糖
fn add x y -> Int = x + y
```

函数是一等公民，所有表达式都返回一个值。

### 3.2 代数数据类型和模式匹配

```aurora
data Option a = Some a | None

fn map<a, b, e>(
  f: a -> b / e,
  opt: Option a
) -> Option b / e =
  match opt {
    Some x -> Some(f(x))
    None   -> None
  }
```

### 3.3 记录与行多态

```aurora
let alice = { name = "Alice", age = 30 }

fn greet(person: { name: String | r }) -> String =
  "Hello, " ++ person.name

greet(alice) // 可以传入带有额外字段的记录
```

### 3.4 Typeclass

```aurora
class Eq a where
  eq: a -> a -> Bool

instance Eq Int where
  eq x y = int_eq(x, y)

instance Eq a => Eq (List a) where
  eq xs ys = ...
```

Typeclass 提供受约束多态，同时避免过度依赖对象继承。

---

## 4. 类型系统

### 4.1 函数类型与效应行

函数类型的基本形式：

```aurora
a -> b / e
```

其中：

- `a` 是参数类型
- `b` 是返回类型
- `e` 是效应行，表示函数可能产生的副作用

纯函数可以省略效应行：

```aurora
fn square(x: Int) -> Int = x * x
```

等价于：

```aurora
fn square(x: Int) -> Int / {} = x * x
```

效应行支持多态：

```aurora
fn map<a, b, e>(
  f: a -> b / e,
  xs: List a
) -> List b / e = ...
```

### 4.2 线性类型

Aurora 使用线性类型管理资源。例如，文件句柄不能被复制或丢弃：

```aurora
fn open(path: String) -> File / {IO}
fn read_line(f: File) -o (String, File) / {IO}
fn close(f: File) -o () / {IO}
```

`-o` 表示线性函数：参数必须被恰好使用一次。这样可以避免资源泄漏和 use-after-close 问题。

### 4.3 推导规则

Aurora 类型系统大致包含：

- Hindley-Milner 类型推断
- 行多态：记录、变体、效应行
- Typeclass 约束求解
- 线性类型检查
- 效应行推断

公开函数要求显式类型签名，内部函数可以充分推断。

---

## 5. 效应系统与代数效应

Aurora 的副作用不是通过异常或隐式可变变量实现，而是通过**代数效应**。

### 5.1 声明效应

```aurora
effect State s where
  get: () -> s
  put: s -> ()

effect Reader r where
  ask: () -> r
```

### 5.2 使用效应

```aurora
fn counter() -> Int / {State Int} = {
  let n = get()
  put(n + 1)
  n
}
```

如果函数内部使用了 `get` 或 `put`，其类型中必须包含 `{State Int}`。

### 5.3 处理效应

效应由 `handle` 块处理：

```aurora
effect Reader r where
  ask: () -> r

fn greeting() -> String / {Reader String} =
  "Hello, " ++ ask()

let result =
  handle greeting() with {
    ask () -> k => k("Aurora")
  }

// result == "Hello, Aurora"
```

`k` 是 continuation，可以恢复计算。由于 continuation 是一等公民，同一个效应可以有不同处理器。

例如，状态效应有内置处理器：

```aurora
let (result, final_state) = run_state(0, counter())
```

### 5.4 多效组合

```aurora
fn compute() -> Int / {Reader String, State Int} = {
  let env = ask()
  let n = get()
  put(n + 1)
  n
}
```

效应行让多个副作用在类型层面清晰组合。

---

## 6. 并发模型

Aurora 默认不共享内存，而是采用如下并发模型：

### 6.1 轻量进程

```aurora
fn main() -> () / {Async, IO} = {
  let ch = channel()
  
  spawn(fn() => send(ch, 42))
  
  let v = receive(ch)
  println(v)
}
```

进程之间通过类型化通道通信。

### 6.2 STM

当确实需要共享可变状态时，使用软件事务内存：

```aurora
let counter = tvar(0)

atomically {
  let v = read_tvar(counter)
  write_tvar(counter, v + 1)
}
```

STM 保证事务的原子性和一致性，避免锁。

### 6.3 数据并行

```aurora
let data = [1, 2, 3, 4]
let result = par_map(fn(x) => x * x, data)
```

提供 `par_map`、`par_fold` 等高层并行操作。

---

## 7. 元编程

Aurora 提供卫生宏与编译期计算：

```aurora
macro logged(expr) = quote {
  let value = expr
  println("value = " ++ show(value))
  value
}

let x = logged(2 + 3)
```

宏在编译期展开，避免运行时成本，同时保持卫生性，避免符号污染。

---

## 8. 工具链与生态

设计上附带：

- `aur`：包管理和构建工具
- `aurora`：REPL 与编译器
- LSP：编辑器支持
- 格式化工具
- 内置测试框架
- 标准库：List、Option、Result、Map、Set、Stream、Parser、STM 等

---

## 9. 与现有语言的区别

| 特性 | Aurora | Haskell | OCaml | Rust |
|------|--------|---------|-------|------|
| 默认求值 | 严格 | 惰性 | 严格 | 严格 |
| 副作用管理 | 效应行+代数效应 | Monad | 自由 | 所有权 |
| 资源管理 | 线性类型 | Monad/Region | GC | 所有权 |
| 类型推断 | 行多态+效应行 | HM+类型类 | HM+模块 | 局部 |
| 并发 | 进程+STM | STM | 通常库级 | 所有权+线程 |

Aurora 的设计目标不是“堆砌特性”，而是让副作用可见、资源安全、并发简单，同时保持函数式编程的清晰表达力。

---

## 10. 一个综合示例

```aurora
effect Logger where
  log: String -> ()

effect State Int where
  get: () -> Int
  put: Int -> ()

fn fibonacci(n: Int) -> Int / {Logger, State Int} = {
  log("computing fib(" ++ show(n) ++ ")")
  
  if n < 2 then {
    n
  } else {
    fibonacci(n - 1) + fibonacci(n - 2)
  }
}

fn main() -> () / {IO} = {
  let result = run_state(0, fibonacci(10))
  
  let final_result =
    handle result with {
      log msg -> k => {
        println("[LOG] " ++ msg)
        k()
      }
    }
  
  println(final_result)
}
```

这个例子展示了：

- 纯函数式递归
- 效应行：`{Logger, State Int}`
- 效应处理器
- 状态线程

---

这是 Aurora 的初步设计草案。核心是：**可以用普通函数风格编写业务逻辑，同时让副作用、资源和并发都处在类型系统的控制之下。**
