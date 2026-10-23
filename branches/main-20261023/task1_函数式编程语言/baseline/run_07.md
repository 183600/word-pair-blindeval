# 任务1 函数式编程语言 | 条件: baseline | 第 7 次

**Prompt:** 设计一个全新的函数式编程语言

**耗时:** 233.85s | **tokens:** 92/1273

---

# Lumen —— 一门全新的函数式编程语言设计

## 一、设计哲学

Lumen 的核心理念是 **"显式的纯度，隐式的复杂性"**：

1. **默认纯函数**，副作用必须通过类型系统显式声明
2. **代数数据类型 + 模式匹配** 作为核心抽象
3. **效果系统（Effect System）** 替代 Monad 栈，让副作用可组合、可推断
4. **编译期保证**：无空指针、无未处理异常、无数据竞争

---

## 二、基本语法

```lumen
-- 函数定义（类型签名可选，编译器可推断）
let add : Int -> Int -> Int
let add x y = x + y

-- 柯里化与管道
let result =
  [1, 2, 3, 4, 5]
    |> filter (\x -> x % 2 == 0)
    |> map (mul 10)
    |> fold (+) 0

-- 不可变绑定与局部作用域
let x = 10
let y =
  let temp = x * 2
  temp + 1
```

---

## 三、代数数据类型与模式匹配

```lumen
-- 类型定义
type Shape =
  | Circle Float
  | Rect Float Float
  | Polygon (List Point)

-- 模式匹配
let area shape =
  match shape with
  | Circle r      -> pi * r * r
  | Rect w h      -> w * h
  | Polygon pts   -> shoelace pts

-- 编译器检查穷尽性，遗漏分支直接报错
-- 没有 null，用 Option 表达缺失
type Option a = Some a | None
```

---

## 四、效果系统（核心创新）

副作用写在类型里，像标签一样组合：

```lumen
-- 读取文件：类型明确标注 IO 效果
let readConfig : String -> String ! {IO, Error}
let readConfig path =
  let! content = File.read path   -- let! 自动传播效果
  parse content

-- 效果可以自由组合，编译器追踪
let main : () -> () ! {IO, Net, Log}
let main () =
  with Log.toConsole            -- 效果处理器（handler）
  with Net.retry 3
  do
    let cfg = readConfig "app.toml"
    serve cfg.port
```

**优势**：无需 Monad transformer 栈，效果是结构化的、可静态分析的。测试时可以注入 mock handler：

```lumen
test "读取配置" =
  with File.mock [("app.toml", fakeContent)]
  do assert (readConfig "app.toml") == expected
```

---

## 五、并发模型：结构化并发 + 不可变数据

```lumen
let fetchAll urls =
  parallel                     -- 结构化并发块
    urls |> map (\url -> spawn (Http.get url))
  -- 所有任务在此汇合，任一失败则全部取消

-- 数据默认不可变，可安全跨线程共享，零数据竞争
-- 可变状态只能通过 Actor 表达
actor Counter =
  state count : Int
  on Increment -> count + 1
  on Get reply -> reply count; count
```

---

## 六、类型系统特性

- **Hindley-Milner 全类型推断**，标注可选
- **行多态记录**（structural records）：
  ```lumen
  let greet p = "Hello, " ++ p.name
  -- 推断为：{ name : String | r } -> String
  ```
- **细化类型（Refinement Types）**（可选标注）：
  ```lumen
  let divide : (x : Int) -> (y : Int where y != 0) -> Int
  ```
- **泛型与类型类（trait）**：
  ```lumen
  trait Show a where show : a -> String
  impl Show Int where show = Int.toString
  ```

---

## 七、其他亮点

| 特性 | 说明 |
|---|---|
| **无异常** | 错误一律用 `Result a e`，效果系统追踪 |
| **尾调用优化** | 保证尾递归不爆栈 |
| **惰性按需** | 默认严格求值，`lazy` 关键字显式惰性 |
| **编译到原生 + WASM** | LLVM 后端 |
| **工具链内置** | 格式化、测试、包管理、LSP 开箱即用 |
| **渐进式学习曲线** | 初级用法看起来像 Python，高级特性按需引入 |

---

## 八、一个完整示例

```lumen
module TodoApp

type Task = { id : Int, title : String, done : Bool }

type Msg = Add String | Toggle Int | Delete Int

let update : Msg -> List Task -> List Task
let update msg tasks =
  match msg with
  | Add title  -> { id = nextId tasks, title, done = False } :: tasks
  | Toggle id  -> map (\t -> if t.id == id then { t | done = not t.done } else t) tasks
  | Delete id  -> filter (\t -> t.id != id) tasks

let main () =
  with Storage.local "tasks.db"
  do App.run { init = [], update, view = Html.render }
```

---

**总结**：Lumen 的差异化在于——用**效果系统**取代 Monad 栈降低副作用管理的认知负担，用**穷尽性检查 + 无 null** 消灭整类运行时错误，用**结构化并发 + 不可变数据**让并行编程默认安全。它试图回答一个问题：*能否让"正确性"成为阻力最小的路径？*

需要我深入展开某一部分吗（比如效果系统的形式化语义、类型推断算法、或编译器架构）？
