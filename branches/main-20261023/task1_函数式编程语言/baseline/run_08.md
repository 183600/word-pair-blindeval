# 任务1 函数式编程语言 | 条件: baseline | 第 8 次

**Prompt:** 设计一个全新的函数式编程语言

**耗时:** 187.03s | **tokens:** 92/1507

---

# 🌿 设计语言：Lumen

> **"让正确性自然发生"** —— 一门为推理而生的纯函数式语言

---

## 一、设计哲学

1. **默认纯函数**：副作用必须显式声明，编译器强制隔离
2. **类型即文档**：类型系统强到可以证明业务规则
3. **零样板代码**：语法层面消除 getter/setter、null 检查等噪音
4. **渐进式严谨**：从脚本快速原型平滑过渡到大型系统

---

## 二、基础语法

### 2.1 函数定义

```lumen
-- 类型签名（可选，编译器可推断）
add : Int -> Int -> Int
add a b = a + b

-- 管道风格
process data =
    data
    |> filter isValid
    |> map normalize
    |> sortBy .priority
    |> take 10
```

### 2.2 数据类型（代数数据类型）

```lumen
type Shape =
    | Circle  { radius : Float }
    | Rect    { width : Float, height : Float }
    | Polygon { points : List Point }

-- 模式匹配
area : Shape -> Float
area shape = case shape of
    Circle r        -> pi * r * r
    Rect w h        -> w * h
    Polygon pts     -> polygonArea pts
```

### 2.3 空值安全 —— 没有 null

```lumen
type Maybe a = Just a | Nothing

findUser : Id -> Maybe User

-- 编译器强制处理两种情况
greet maybeUser = case maybeUser of
    Just user -> "Hello, {user.name}!"
    Nothing   -> "Hello, stranger."
```

---

## 三、核心创新特性

### 3.1 效果系统（Effect System）⭐

副作用写在类型里，像类型一样被检查和组合：

```lumen
-- 这个函数会做 IO 和数据库操作，类型里一目了然
fetchAndSave : Url -> {IO, DB} Result

-- 纯函数无法调用它，除非也声明这些效果
processData : Data -> Data               -- 纯函数
logAndSave : Data -> {IO, DB} Unit       -- 有副作用

-- 效果可以被"处理"（类似依赖注入）
handleIO : {IO} a -> IO a
```

### 3.2 细化类型（Refinement Types）

把业务规则编码进类型：

```lumen
type Email    = String where matches emailRegex
type Age      = Int where 0 <= _ <= 150
type NonEmpty a = List a where length _ > 0

-- 编译期拒绝非法值，无需运行时检查
sendWelcome : Email -> Age -> {IO} Unit
sendWelcome "not-an-email" 25   -- ❌ 编译错误！
sendWelcome "a@b.com" 200       -- ❌ 编译错误！
```

### 3.3 隐式并发

纯函数天然可并行，编译器自动优化：

```lumen
-- 自动并行化，无需手动管理线程
results = parMap expensiveCompute hugeList

-- 异步用 async/await 语法糖
fetchAll : List Url -> {IO, Async} List Response
fetchAll urls = async
    responses <- gather (map fetch urls)
    return responses
```

### 3.4 结构化记录与无样板更新

```lumen
type User = { name : String, age : Age, tags : List String }

user = { name: "Ada", age: 36, tags: ["admin"] }

-- 不可变更新，语法极简
older  = user with age += 1
tagged = user with tags ~= push "vip"
```

---

## 四、类型系统

| 特性 | 说明 |
|---|---|
| **Hindley-Milner 推断** | 几乎不需要手写类型标注 |
| **泛型与约束** | `sort : Ord a => List a -> List a` |
| **依赖对（轻量）** | 列表长度可进入类型：`Vector n a` |
| **行多态记录** | 函数可接受"任何含 name 字段的记录" |

```lumen
-- 行多态：接受任何有 name 字段的记录
greet : { name : String | r } -> String
greet record = "Hi, {record.name}"
```

---

## 五、模块与错误处理

```lumen
module Shop.Cart exposing (addItem, checkout)

-- 错误是值，不是异常
type Result e a = Ok a | Err e

checkout : Cart -> {DB} Result CheckoutError Receipt

-- ? 操作符自动传播错误
placeOrder cart = do
    receipt  <- checkout cart ?
    _        <- sendEmail receipt ?
    return receipt
```

---

## 六、一个完整示例：Todo 服务

```lumen
type Todo = { id : Id, title : NonEmpty String, done : Bool }

type AppError = NotFound Id | InvalidTitle | DbError String

addTodo : String -> {DB} Result AppError Todo
addTodo rawTitle = do
    title  <- validateTitle rawTitle ?        -- 细化类型验证
    todo   <- db.insert { title, done: False } ?
    log.info "Created {todo.id}"
    return todo

main : {IO, DB} Unit
main =
    serve port: 8080
        [ POST "/todos" -> withBody addTodo
        , GET  "/todos" -> listTodos
        ]
```

---

## 七、工具链设计

| 工具 | 功能 |
|---|---|
| `lumen build` | 增量编译，错误信息带修复建议 |
| `lumen fmt` | 唯一官方格式，终结风格之争 |
| `lumen test` | 内置属性测试（property-based testing） |
| `lumen prove` | 对细化类型做形式化验证 |
| `lumen repl` | 交互式探索，支持类型查询 `:type` |

---

## 八、与现有语言的差异

| 对比 | Lumen 的取舍 |
|---|---|
| vs Haskell | 效果系统更直观，无 Monad 栈地狱 |
| vs Elm | 面向后端与通用场景，不限于前端 |
| vs Rust | 无所有权心智负担，GC + 区域内存混合管理 |
| vs TypeScript | 类型不可逃逸，没有 `any` 后门 |

---

**总结**：Lumen 的核心理念是——**把运行时的 bug 左移到编译期，把编译期的复杂度留给编译器**。副作用可见、空值不存在、规则写进类型，让开发者专注于问题本身。

需要我深入展开某个部分吗？比如效果系统的形式化定义、编译器实现思路，或者标准库设计？
