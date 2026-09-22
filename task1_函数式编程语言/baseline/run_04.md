# 任务1 函数式编程语言 | 条件: baseline | 第 4 次

**Prompt:** 设计一个全新的函数式编程语言

**耗时:** 174.67s | **tokens:** 92/1609

---

# Lumen —— 一门全新的函数式编程语言

## 一、设计理念

**核心哲学：「数据如光，流动即计算」**

Lumen 围绕三个原则设计：

1. **管道优先（Pipeline-First）**：所有计算本质上是数据的流动变换，管道是一等公民
2. **效果透明（Effect Transparency）**：副作用必须在类型签名中显式声明
3. **渐进式类型（Gradual Soundness）**：类型系统从"完全推断"到"依赖类型"可自由选择强度

---

## 二、基础语法

### 2.1 值与绑定

```lumen
-- 不可变绑定（默认）
let pi = 3.14159

-- 类型标注（可选，通常可推断）
let name: String = "Lumen"

-- 可变绑定需要显式声明（且被类型系统追踪）
let mut counter = 0
```

### 2.2 函数

```lumen
-- 基本函数
let add = fn (x, y) => x + y

-- 多行函数
let factorial = fn (n) =>
  if n <= 1 then 1
  else n * factorial(n - 1)

-- 柯里化是默认行为
let add5 = add(5)        -- 部分应用
let result = add5(3)     -- 8
```

### 2.3 管道操作符（语言的核心）

```lumen
-- |> 前向管道
[1, 2, 3, 4, 5]
  |> map(fn x => x * x)
  |> filter(fn x => x > 4)
  |> sum                    -- 54

-- 占位符语法：_ 表示数据注入位置
fetch(url)
  |> parse_json(_)
  |> .users
  |> sort_by(_.age)
```

---

## 三、类型系统

### 3.1 代数数据类型

```lumen
type Shape =
  | Circle(radius: Float)
  | Rect(width: Float, height: Float)
  | Point

-- 模式匹配
let area = fn shape =>
  match shape with
  | Circle(r)      => pi * r * r
  | Rect(w, h)     => w * h
  | Point          => 0.0
  -- 编译器检查穷尽性
```

### 3.2 效果类型（核心创新）

副作用写在类型里，用 `!` 标注：

```lumen
-- 纯函数
let square: Int -> Int

-- 带 IO 效果的函数
let read_file: Path -> String ! {IO}

-- 组合效果
let handler: Request -> Response ! {IO, State<Db>, Throws<HttpError>}

-- 效果处理（类似代数效果）
handle
  process_data()
with
  | IO.read(path)  => resume(cache.get(path))
  | Throws(e)      => log(e); default_value
```

### 3.3 细化类型（可选开启）

```lumen
-- 编译期验证的约束
let divide: (x: Float, y: Float where y != 0) -> Float

type PositiveInt = Int where self > 0

let head: (list: List<a> where list.len > 0) -> a
```

---

## 四、并发模型：光流（Streams）

```lumen
-- 惰性流
let naturals = Stream.iterate(0, fn x => x + 1)

naturals
  |> Stream.filter(is_prime)
  |> Stream.take(10)
  |> Stream.to_list

-- 结构化并发：所有任务必须在 scope 内完成
let results = scope fn s =>
  let a = s.spawn(fn => fetch_user(id))
  let b = s.spawn(fn => fetch_orders(id))
  (await a, await b)

-- 通道通信
let (tx, rx) = Channel.new(capacity: 16)
```

---

## 五、独特的语法特性

### 5.1 时间旅行调试注解

```lumen
@trace
let complex_calculation = fn data =>
  data |> step1 |> step2 |> step3
-- 运行时自动记录每一步的中间值，可回放
```

### 5.2 编译期计算（Comptime）

```lumen
comptime let lookup_table = build_table(1000)

-- 编译期正则
let email_regex = comptime regex"^[\w.]+@[\w.]+$"

-- 编译期 SQL 校验
let query = comptime sql"SELECT * FROM users WHERE id = ?"
-- 连接 schema 在编译期验证 SQL 合法性
```

### 5.3 单位类型（Units of Measure）

```lumen
let distance = 100.0<km>
let time = 2.0<h>
let speed = distance / time        -- 50.0<km/h>

let error = distance + time        -- ❌ 编译错误：单位不匹配
```

---

## 六、模块与包管理

```lumen
-- 模块即文件
module Geometry

export { area, perimeter }

import Math.{pi, sqrt}
import Http as H

-- 依赖声明内嵌在源码中（单文件可运行）
-- deps: json@2.1, http@3.0
```

---

## 七、完整示例：一个 Web 服务

```lumen
-- deps: web@1.0

module Main

type User = { id: Int, name: String, email: String }

let get_user: Int -> User ! {IO, Throws<NotFound>} = fn id =>
  Db.query("SELECT * FROM users WHERE id = ?", [id])
    |> first
    |> or_throw(NotFound)

let routes = [
  GET "/users/:id" => fn req =>
    req.params.id
      |> parse_int
      |> and_then(get_user)
      |> map(to_json)
      |> respond(200)
      |> rescue(fn NotFound => respond(404, "User not found"))
]

let main = fn () ! {IO} =>
  Web.serve(routes, port: 8080)
    |> tap(fn _ => log("Server started on :8080"))
```

---

## 八、设计决策总结

| 特性 | 决策 | 理由 |
|------|------|------|
| 求值策略 | 默认严格，显式惰性 | 性能可预测 |
| 可变性 | 默认不可变，`mut` 显式标记 | 减少 bug |
| 空值 | 无 null，用 `Option<a>` | 消灭空指针异常 |
| 错误处理 | `Result` + 效果系统 | 错误也是类型 |
| 并发 | 结构化并发 + 不可变消息 | 无数据竞争 |
| 互操作 | WASM 一等支持，FFI 调用 C | 生态兼容 |

---

## 九、与现有语言的差异化

- **vs Haskell**：效果系统更轻量，语法更友好，无 Monad 门槛
- **vs Elm**：不局限于前端，效果系统更通用
- **vs F#/OCaml**：管道优先的语法设计，效果类型内建
- **vs Gleam**：支持编译期计算和细化类型

想让我深入展开某个部分吗？比如效果系统的形式化语义、类型推导算法，或者写一个更复杂的示例程序？
