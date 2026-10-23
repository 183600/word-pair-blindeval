# 任务1 函数式编程语言 | 条件: baseline | 第 1 次

**Prompt:** 设计一个全新的函数式编程语言

**耗时:** 278.16s | **tokens:** 92/1628

---

# Lumen —— 一门全新的函数式编程语言设计

## 一、设计哲学

Lumen 的核心信条是：**"让正确性成为默认，让副作用显式流动"**。

三大支柱：
1. **一切皆是表达式** —— 没有语句，没有隐式返回
2. **效果即类型** —— 副作用（IO、状态、异常）全部编码在类型系统中
3. **渐进式严格** —— 从快速原型到形式化验证，同一门语言平滑过渡

---

## 二、基础语法

```lumen
-- 绑定（默认不可变）
let pi = 3.14159

-- 函数定义
let square = fn x -> x * x

-- 简写形式
let double x = x * 2

-- 管道操作符（核心惯用法）
[1, 2, 3, 4]
  |> map (fn x -> x * x)
  |> filter (fn x -> x > 4)
  |> sum          -- 结果: 25

-- 一切都是表达式
let result = if score > 60 then "pass" else "fail"

let area = match shape with
  | Circle r      -> pi * r * r
  | Rect w h      -> w * h
  | Triangle b h  -> b * h / 2
```

---

## 三、类型系统

### 3.1 代数数据类型（ADT）

```lumen
type Option a =
  | Some a
  | None

type Result e a =
  | Ok a
  | Err e

-- 广义代数数据类型（GADT）
type Expr a where
  | Lit  : Int -> Expr Int
  | Add  : Expr Int -> Expr Int -> Expr Int
  | Eq   : Expr Int -> Expr Int -> Expr Bool
```

### 3.2 行多态记录（Row Polymorphism）

```lumen
-- 函数只声明它需要的字段，接受任何包含这些字段的记录
let greet : { name : String | r } -> String
let greet person = "Hello, " ++ person.name

greet { name = "Ada", age = 36 }   -- ✓ 合法
```

### 3.3 依赖类型（可选层级）

```lumen
-- Level 0: 普通类型
let head : List a -> Maybe a

-- Level 1: 精炼类型
let divide : (x : Int, y : Int where y != 0) -> Int

-- Level 2: 完整依赖类型
let replicate : (n : Nat) -> a -> Vector n a
```

---

## 四、效果系统（Lumen 的核心创新）

副作用不是 monad，而是**类型中的效果行**：

```lumen
-- 类型签名直接宣告效果
let readFile : Path -> String ! {IO, Throws FileError}

let launchMissiles : Code -> Unit ! {IO, Network, Unsafe}

-- 效果可以自由组合与处理
let program : Unit ! {IO}
let program =
  with handler
    | Throw e -> log e; retry
  in
    readFile "config.toml"
```

效果推导是自动的——**纯函数永远不可能偷偷做 IO**，编译器保证。

---

## 五、并发模型：结构化并发 + 不可变数据

```lumen
-- 数据不可变，共享零成本，无数据竞争
let results =
  parallel
    [ async fetch url1
    , async fetch url2
    , async fetch url3
    ]
  |> awaitAll        -- 任一失败则全部取消

-- 通道通信（CSP 风格）
let producer chan =
  loop 0 fn n ->
    if n < 10 then
      send chan n
      recur (n + 1)
    else
      close chan
```

---

## 六、独特特性

### 6.1 空洞驱动开发（Hole-Driven Development）

```lumen
let solve problem =
  problem
    |> normalize
    |> ?applyRules      -- 编译器给出该位置的类型与建议
    |> ?verify
```

编译器会提示：`?applyRules : NormalForm -> Derivation`，甚至自动填充候选实现。

### 6.2 编译期计算（CTFE）

```lumen
-- comptime 块在编译期求值
let primes = comptime sieve 1000

-- 类型级编程无需模板元编程的技巧
type Matrix (r : Nat) (c : Nat) = ...
```

### 6.3 量词感知模式匹配

```lumen
match json with
  | { "users": [..rest, last] } -> last   -- 序列模式
  | { "error": msg }            -> panic msg
```

---

## 七、模块系统

```lumen
module Geometry exposing (Shape(..), area, perimeter)

import Data.Map as Map
import Json exposing (decode, encode)

-- 函子（参数化模块）
module MakeCache (K : Hashable) (V : Type) =
  type Cache = ...
  let get k cache = ...
```

---

## 八、错误处理哲学

**没有异常，没有 null**。只有数据：

```lumen
let config =
  readFile "app.toml"
    |> andThen parseToml
    |> andThen validate
    |> unwrapOr defaultConfig

-- ? 语法糖：自动短路
let loadUser id =
  let conn   = connect db ?
  let row    = query conn id ?
  parseUser row
```

---

## 九、完整示例：一个迷你 Web 服务

```lumen
module Main

type Route =
  | Home
  | User Int

let router : Request -> Route
let router req = match req.path with
  | "/"          -> Home
  | "/user/" + id -> User (parseInt id)

let handle : Route -> Response ! {IO, DB}
let handle route = match route with
  | Home    -> html "<h1>Welcome</h1>"
  | User id ->
      let user = findUser id ?
      json { name = user.name }

let main : Unit ! {IO}
let main =
  serve (port = 8080) (router >> handle)
```

---

## 十、与现有语言的对比

| 特性 | Haskell | OCaml | Elm | **Lumen** |
|------|---------|-------|-----|-----------|
| 效果系统 | Monad/IO | 无 | 受限 | **效果行 + 处理器** |
| 依赖类型 | 扩展拼凑 | 无 | 无 | **原生分层** |
| 求值策略 | 惰性 | 严格 | 严格 | **严格 + 显式惰性** |
| 空洞驱动 | 部分 | 无 | 无 | **一等公民** |
| 学习曲线 | 陡峭 | 中等 | 平缓 | **渐进式** |

---

## 总结

Lumen 试图回答一个问题：**如果今天从零设计一门函数式语言，汲取 Haskell 的纯粹、OCaml 的实用、Elm 的友好、Idris 的表达力，会是什么样子？**

答案是：一门效果显式、类型分层、工具链友好、从脚本到定理证明都能胜任的语言。

想要我深入展开某一部分吗？比如效果系统的形式化语义、类型推导算法，或者写一个更完整的示例程序？
