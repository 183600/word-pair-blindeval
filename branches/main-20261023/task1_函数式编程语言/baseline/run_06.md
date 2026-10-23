# 任务1 函数式编程语言 | 条件: baseline | 第 6 次

**Prompt:** 设计一个全新的函数式编程语言

**耗时:** 144.85s | **tokens:** 92/1251

---

# 🌊 Flux —— 一门全新的函数式编程语言

## 设计理念

> **"数据如河流，函数如河床"**

Flux 的核心思想：把一切计算建模为**带有时间维度的数据流**，同时保持纯函数式的严谨性。它试图回答一个问题：*如果 Haskell 的纯度、Elm 的易用性、和 Rust 的所有权模型生了一个孩子，会怎样？*

---

## 1. 核心特性一览

| 特性 | 说明 |
|------|------|
| 默认纯函数 | 副作用必须通过 effect 声明 |
| 流是一等公民 | `Stream a` 与 `List a` 平级 |
| 线性类型可选 | 资源安全，无 GC 停顿 |
| 代数效应 | 取代 monad 栈 |
| 编译期求值 | `comptime` 块在编译时运行 |

---

## 2. 基本语法

```flux
-- 函数定义：管道风格
let double = fn x -> x * 2

-- 类型推断，但可标注
let add : Int -> Int -> Int
let add = fn a b -> a + b

-- 管道操作符是语言核心
let result =
    [1, 2, 3, 4, 5]
    |> map (fn x -> x * 2)
    |> filter (fn x -> x > 4)
    |> sum          -- 14
```

## 3. 代数效应（取代 Monad 栈）

```flux
-- 声明效应
effect Logger
    log : String -> ()

effect Http
    get : Url -> Response ! {Network, Fail}

-- 使用效应：函数签名自动携带
let fetchUser : UserId -> User ! {Http, Logger}
let fetchUser = fn id ->
    do Logger.log "fetching..."
    response <- perform Http.get (urlFor id)
    decode response.body

-- 处理效应：像模式匹配一样
handle fetchUser 42 with
| Logger.log msg, resume ->
    print msg
    resume ()
| Http.get url, resume ->
    resume (mockResponse url)   -- 测试时注入假实现
```

## 4. 流（Stream）—— 时间的类型化表达

```flux
-- 冷热流区分
let clicks : Stream MouseEvent = UI.clicks button

-- 流可以像列表一样变换，但保留时序语义
let throttled =
    clicks
    |> Stream.throttle 100.ms
    |> Stream.map (.position)

-- 流的汇合：声明式并发
let combined =
    Stream.zip3 mousePos keyboardState clock
    |> Stream.sampleEvery 16.ms
    |> Stream.run renderFrame
```

## 5. 线性类型与资源安全

```flux
-- 线性资源：编译器保证恰好使用一次
let processFile : linear File -> Result Data
let processFile = fn file ->
    let contents = File.read file   -- file 被消耗
    parse contents
    -- 忘记 close？不存在 —— 消耗即关闭

-- 借用：只读访问不消耗
let peek : borrow File -> Metadata
```

## 6. 模式匹配 + 视图（View Patterns 进化版）

```flux
let describe = fn shape ->
    match shape with
    | Circle r where r > 10     -> "big circle"
    | Circle _                  -> "small circle"
    | Rect (w, h) where w == h  -> "square in disguise"
    | Polygon [p] as singleton  -> "degenerate: {p}"
    | Polygon points
        |> count -> n where n > 100 -> "complex polygon"
    | _ -> "something else"
```

## 7. 编译期计算

```flux
-- comptime 块在编译期执行，结果内联
let router = comptime
    routes
    |> validateNoConflicts
    |> buildTrie          -- 生成最优匹配结构

-- 类型级编程变得自然
let Matrix (rows: Nat) (cols: Nat) a = ...
let multiply : Matrix m n a -> Matrix n p a -> Matrix m p a
-- 维度不匹配 = 编译错误
```

## 8. 一个完整的小例子：并发计数服务

```flux
module Counter

effect State
    get : () -> Int
    put : Int -> ()

let increment : () -> Int ! {State}
let increment = fn () ->
    n <- perform State.get ()
    do perform State.put (n + 1)
    n + 1

-- 运行：状态处理 + 并发
let main =
    Stream.interval 1.s
    |> Stream.map (fn _ -> increment ())
    |> Stream.runParallel workers: 4
    |> handleState initial: 0
    |> Stream.fold print
```

---

## 设计决策背后的权衡

1. **为什么用代数效应而非 Monad？** —— 效应可自由组合，无需 monad transformer 的样板代码；测试时注入 mock 极其自然。
2. **为什么流是内置的？** —— 现代程序（UI、服务器、数据管道）本质是流处理，不该是库的事后补充。
3. **为什么线性类型是"可选"的？** —— 只在需要资源安全的地方付出认知成本，其余代码享受 GC 的便利。

---

要不要我深入展开某一部分？比如：
- 完整的类型系统形式化（Hindley-Milner + 线性扩展）
- 效应系统的实现原理
- 与 Haskell / OCaml / Gleam 的详细对比
- 写一个更复杂的示例项目（如 HTTP 服务器）
