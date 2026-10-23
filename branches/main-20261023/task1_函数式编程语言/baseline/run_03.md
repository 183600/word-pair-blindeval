# 任务1 函数式编程语言 | 条件: baseline | 第 3 次

**Prompt:** 设计一个全新的函数式编程语言

**耗时:** 161.29s | **tokens:** 92/1421

---

# Lumen —— 一门全新的函数式编程语言设计

## 一、设计理念

Lumen 的核心信条是：**"让正确的代码最容易写，让错误的状态无法表示"**。

三个设计支柱：
1. **全函数式，但有实用主义的逃生舱**
2. **效果即类型（Effects as Types）**——副作用在类型系统中完全可见
3. **数据流优先**——为管道式、可组合的代码而生

---

## 二、基本语法

```
-- 注释用双横线
-- 函数定义：name: 参数类型 -> 返回类型
add: Int -> Int -> Int
add x y = x + y

-- 类型推断，可省略签名
square x = x * x

-- 不可变绑定
let pi = 3.14159

-- 管道操作符是语言核心
result = data
  |> filter isEven
  |> map square
  |> sum

-- 反向应用（函数组合）
normalize = trim >> lowercase >> collapseSpaces
```

---

## 三、类型系统

### 代数数据类型（ADT）

```
type Shape =
  | Circle(radius: Float)
  | Rect(width: Float, height: Float)
  | Point

area: Shape -> Float
area shape = case shape of
  Circle(r)  -> pi * r * r
  Rect(w, h) -> w * h
  Point      -> 0.0
```

### 没有 null —— 只有 Option 和 Result

```
type Option a = Some a | None
type Result e a = Ok a | Err e

head: List a -> Option a
head []      = None
head (x::xs) = Some x
```

### 记录类型 + 结构化更新

```
type User = { name: String, age: Int, email: String }

alice = { name = "Alice", age = 30, email = "a@x.com" }
older = { alice | age = 31 }   -- 不可变更新
```

### 细化类型（Refinement Types）—— 特色功能

```
type Percent = Float where 0.0 <= it <= 100.0
type NonEmpty a = List a where length it > 0

-- 编译器在编译期验证约束
discount: Percent -> Float -> Float
```

---

## 四、效果系统（最核心创新）

所有副作用都标注在类型上，用 `!` 表示：

```
-- 纯函数：没有效果标注
add: Int -> Int -> Int

-- 带效果的函数
readFile: Path -> String ! IO
getUser: UserId -> User ! {IO, Throws DbError}
log: String -> Unit ! Console
```

### 效果处理（Algebraic Effects 风格）

```
handle fetchData url with
  | Network err -> useCachedData ()
  | _           -> resume defaultValue

-- 测试时可以注入假效果
runTest = with MockIO in mainProgram
```

效果是可组合、可替换、可测试的——这是 Lumen 区别于 Haskell IO Monad 的关键。

---

## 五、并发模型：无共享 + 结构化并发

```
-- spawn 返回 Channel，类型保证无数据竞争
task fetchAll urls =
  parallel
    ch1 <- spawn (fetch urls[0])
    ch2 <- spawn (fetch urls[1])
    ch3 <- spawn (fetch urls[2])
  collect [ch1, ch2, ch3]   -- 全部完成才返回，无泄漏

-- 流处理是一等公民
stream events
  |> Stream.throttle 100ms
  |> Stream.map process
  |> Stream.fold aggregate
```

---

## 六、模式匹配的增强

```
describe n = case n of
  0             -> "zero"
  x if x < 0    -> "negative"
  [single]      -> "one element"
  [first, ..rest] -> "head: {first}"
  { name, age } if age >= 18 -> "adult {name}"
  _             -> "other"
```

支持：守卫、列表解构、记录解构、**字符串插值**（`"..."` 内 `{expr}`）。

---

## 七、编译期元编程（无宏卫生问题）

```
-- comptime 块在编译期执行，生成代码
comptime
  routes = deriveRoutes Api
  sql    = validateQuery "SELECT * FROM users"  -- 编译期校验 SQL！

-- 编译期就知道 SQL 写错了，而不是运行时崩溃
```

---

## 八、错误处理哲学

```
-- 错误是值，不是异常
divide: Float -> Float -> Result DivByZero Float

-- ? 操作符自动传播错误（类似 Rust）
compute: Input -> Result AppError Output
compute input =
  a <- parse input ?      -- 失败则提前返回 Err
  b <- validate a ?
  Ok (transform b)
```

---

## 九、一个完整示例：迷你 Web 服务

```
type Route = GET "/users/:id" | POST "/users"

server: Route -> Response ! {IO, Console}
server route = case route of
  GET id ->
    db.findUser id
      |> map toJson
      |> default (error 404 "not found")

  POST body ->
    case validate body of
      Ok user -> db.insert user |> map (created 201)
      Err e   -> error 400 e.message

main = run 8080 server
```

---

## 十、设计决策总结

| 特性 | 选择 | 理由 |
|---|---|---|
| 求值策略 | 默认严格，惰性需标注 `lazy` | 性能可预测 |
| 可变性 | 默认不可变，`mut` 仅限局部作用域 | 安全 + 实用 |
| 类型类 | 有（称 `trait`），但禁止孤儿实例 | 一致性 |
| 模块系统 | 文件即模块，显式导出 | 简单 |
| 包管理 | 内置，锁文件强制，内容寻址缓存 | 可复现构建 |
| 工具链 | 单一 `lumen` 命令：构建/测试/格式化/LSP | 零配置 |

**一句话定位**：Lumen = Elm 的友好 + Haskell 的表达力 + Rust 的严谨 + Elixir 的并发，但效果系统让一切副作用透明可控。

需要我深入展开某个部分吗？比如效果系统的形式化语义、编译器架构，或者写更多示例代码？
