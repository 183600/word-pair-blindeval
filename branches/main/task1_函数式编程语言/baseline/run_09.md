# 任务1 函数式编程语言 | 条件: baseline | 第 9 次

**Prompt:** 设计一个全新的函数式编程语言

**耗时:** 234.86s | **tokens:** 92/1817

---

# Lumen —— 一门全新的函数式编程语言设计

## 一、设计理念

**核心哲学：「显式优于隐式，组合优于继承，数据即程序」**

Lumen 的设计目标：
1. **纯函数式核心**，副作用完全显式化
2. **极简语法** —— 关键字少于 20 个
3. **强类型 + 全局类型推断**，但允许渐进式标注
4. **一等公民的并发**，基于不可变数据
5. **可教学** —— 语法规则可以用一页纸讲完

---

## 二、基础语法

### 2.1 值绑定与函数

```lumen
-- 不可变绑定（默认）
let x = 42
let name = "Lumen"

-- 函数定义（即值绑定 + lambda）
let add = fn a b -> a + b

-- 语法糖
let add a b = a + b

-- 类型标注（可选，编译器可推断）
let add : Int -> Int -> Int
let add a b = a + b
```

### 2.2 一切都是表达式

```lumen
let result =
  if x > 0 then "positive"
  elif x < 0 then "negative"
  else "zero"

-- match 也是表达式
let describe n =
  match n with
  | 0 -> "zero"
  | 1 -> "one"
  | _ if n < 0 -> "negative"
  | _ -> "many"
```

### 2.3 管道与组合（核心特色）

```lumen
-- 管道操作符 |>
let result =
  data
  |> filter (fn x -> x > 0)
  |> map (fn x -> x * 2)
  |> sum

-- 函数组合 >>
let process = parse >> validate >> transform >> save

-- 反向应用 <|（少用，但可读性好）
let y = sqrt <| abs <| -16
```

---

## 三、类型系统

### 3.1 代数数据类型（ADT）

```lumen
type Shape =
  | Circle of radius: Float
  | Rect of width: Float, height: Float
  | Point

-- 泛型
type Option a =
  | Some of a
  | None

type Result e a =
  | Ok of a
  | Err of e
```

### 3.2 记录类型（带行多态）

```lumen
type Person = { name: String, age: Int }

let alice = { name = "Alice", age = 30 }

-- 记录更新（产生新值）
let older = { alice | age = 31 }

-- 行多态：函数只关心需要的字段
let greet : { name: String | r } -> String
let greet p = "Hello, " ++ p.name
```

### 3.3 效果系统（Effect System）—— 最大创新点

副作用**编码在类型里**，但用 `with` 优雅处理：

```lumen
-- 类型签名中显式声明效果
let readFile : Path -> String ! {IO, Error}
let readFile path = ...

-- 调用时自动传播效果
let process : Path -> String ! {IO, Error}
let process path =
  let! content = readFile path   -- let! 解包带效果的值
  content |> toUpper

-- 在边界处处理效果
let main : () -> Unit ! {IO}
let main () =
  handle process "data.txt" with
  | Ok s -> print s
  | Err e -> log "failed: {e}"
```

**规则**：纯函数可以调用纯函数；带效果的函数调用后效果自动并集传播；只有 `handle` 能消除效果。

---

## 四、并发模型：无共享 + 结构化并发

```lumen
-- spawn 返回 Task，数据自动深拷贝/结构共享（不可变所以安全）
let task1 = spawn (fn () -> fetch url1)
let task2 = spawn (fn () -> fetch url2)

-- 并发作用域：任一失败全部取消，离开作用域必完成
let results = concurrent
  [ fetch url1
  , fetch url2
  , fetch url3
  ]

-- 通道通信（CSP 风格）
let ch = channel 10
spawn (fn () -> loop (fn () -> send ch (produce ())))
let value = receive ch
```

**保证**：没有数据竞争（数据不可变）、没有孤儿任务（结构化并发）。

---

## 五、特色语法创新

### 5.1 「洞」驱动开发（Hole-driven）

```lumen
let process data =
  data
  |> ?
-- 编译器报错并提示：此处需要 [Int] -> ?，可用函数：sum, length, ...
```

### 5.2 内联测试（测试即文档）

```lumen
let add a b = a + b
test
  add 1 2 == 3
  add 0 0 == 0
  add -1 1 == 0
```

### 5.3 语法级单位（Units of Measure）

```lumen
let distance = 100<m>
let time = 9.58<s>
let speed = distance / time   -- 类型：Float<m/s>
let bad = distance + time     -- 编译错误！
```

### 5.4 惰性流

```lumen
let naturals = iterate (fn x -> x + 1) 0   -- 无限流
let evens = naturals |> Stream.filter even |> Stream.take 10 |> toList
```

---

## 六、模块系统

```lumen
module Geometry exposing (Shape, area, perimeter)   -- 显式导出

import List exposing (map, filter)   -- 显式导入
import Math as M                     -- 别名

-- 无全局命名空间污染，无默认导出，无动态 require
```

---

## 七、错误处理哲学

**没有异常**。所有失败都是值：

```lumen
let divide : Float -> Float -> Result String Float
let divide a b =
  if b == 0.0 then Err "division by zero"
  else Ok (a / b)

-- 用 ? 操作符短路（类似 Rust）
let calculate x y =
  let a = divide x y ?
  let b = divide a 2.0 ?
  Ok (a + b)
```

---

## 八、一个完整示例

```lumen
module TodoApp exposing (main)

type Todo = { id: Int, title: String, done: Bool }

type Msg =
  | AddTodo of String
  | Toggle of Int
  | ClearDone

let update msg todos =
  match msg with
  | AddTodo title ->
      todos ++ [{ id = nextId todos, title = title, done = False }]
  | Toggle id ->
      todos |> map (fn t -> if t.id == id then { t | done = not t.done } else t)
  | ClearDone ->
      todos |> filter (fn t -> not t.done)

let main () =
  run { init = [], update = update, view = view }
```

---

## 九、设计决策总结表

| 决策 | 选择 | 理由 |
|------|------|------|
| 求值策略 | 默认严格 + 显式惰性 | 性能可预测，空间泄漏少 |
| 可变性 | 完全不可变 | 并发安全，推理简单 |
| 空值 | 无 null，用 Option | 消灭十亿美元错误 |
| 异常 | 无，用 Result + 效果 | 错误路径显式可见 |
| 类型类 | 支持（称为 trait） | 受控的临时多态 |
| 宏 | 卫生宏，受限使用 | 元编程但不破坏可读性 |
| GC | 分代 GC + 逃逸分析 | 不可变数据分配频繁，需高效回收 |

---

**Lumen 的一句话定位**：*「像 Elm 一样友好，像 Haskell 一样纯粹，像 Erlang 一样并发，但比他们任何一个都更简单。」*

需要我深入展开某一部分吗？比如效果系统的形式化语义、类型推断算法（Hindley-Milner 扩展），或者编译器架构设计？
