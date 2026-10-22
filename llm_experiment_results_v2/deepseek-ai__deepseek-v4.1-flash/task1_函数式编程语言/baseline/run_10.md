# [v2:deepseek-ai/deepseek-v4.1-flash] 任务1 函数式编程语言 | 条件: baseline | 第 10 次

**Prompt:** 设计一个全新的函数式编程语言

**耗时:** 297.57s | tokens: 37/8192

---

# Aster：一个全新的函数式编程语言设计

## 1. 定位

**Aster** 是一门纯函数式、静态类型、效果显式、结构化并发的通用编程语言。  
目标：让函数式编程既安全又实用。

核心原则：

- 不可变是默认，副作用必须出现在类型里。
- 默认严格求值，惰性显式。
- 用代数效应代替 monad transformer。
- 行多态记录/变体，减少样板代码。
- 结构化并发和线性资源内建。
- 类型推断强，但公共 API 明确。

---

## 2. 语法速览

```aster
module Example

import Std.IO
import Std.List

// 函数
fn add(x: Int, y: Int) -> Int = x + y

// 泛型 + 效果多态
fn map<A, B, E>(f: A -> <E> B, xs: List A) -> <E> List B =
  match xs {
    [] => []
    x :: rest => f(x) :: map(f, rest)
  }

// 管道与组合
let result =
  [1, 2, 3, 4]
  |> List.map(fn(x) => x * 2)
  |> List.filter(fn(x) => x > 4)
  |> List.sum
```

记录与变体：

```aster
type User = { id: Int, name: String, email: Option String }

let u = { id = 1, name = "Ada", email = None }
let u2 = { u with name = "Ada Lovelace" }

type Shape =
  | Circle { radius: Float }
  | Rect { width: Float, height: Float }

fn area(shape: Shape) -> Float =
  match shape {
    Circle { radius } => 3.14159 * radius * radius
    Rect { width, height } => width * height
  }
```

类型类：

```aster
trait Show a {
  fn show(x: a) -> String
}

impl Show Shape {
  fn show(shape) = match shape {
    Circle { radius } => "Circle({radius})"
    Rect { width, height } => "Rect({width}, {height})"
  }
}
```

---

## 3. 类型系统

- 基础类型：`Int`, `Float`, `Bool`, `String`, `Unit`, `Never`
- 容器：`List a`, `Option a`, `Result e a`, `Map k v`
- 函数：`(A, B) -> <E> C`，其中 `E` 是效果行。纯函数写 `(A) -> B`
- 记录：`{ x: Int, y: Int | ρ }`，支持行多态
- 变体：`[A | B | ρ]`，支持开放变
