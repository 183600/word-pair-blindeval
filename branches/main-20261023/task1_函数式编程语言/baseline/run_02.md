# 任务1 函数式编程语言 | 条件: baseline | 第 2 次

**Prompt:** 设计一个全新的函数式编程语言

**耗时:** 241.94s | **tokens:** 92/1225

---

# 🌊 Flux — 一门全新的函数式编程语言

**设计理念**：让数据像水流一样穿过程序，类型系统像护栏一样保护你，但永远不挡路。

---

## 一、核心哲学

1. **一切皆是流（Stream）** — 值是流的特例（单元素流）
2. **默认不可变，显式可变** — 可变性必须声明意图
3. **错误即数据** — 没有异常，只有 `Result` 流
4. **缩进即结构**，符号最少化

---

## 二、基础语法

### 值与绑定
```flux
-- 不可变绑定
let pi = 3.14159

-- 显式可变（少见，需声明）
var counter = 0

-- 类型注解（可选，编译器全量推断）
let name: Text = "Flux"
```

### 函数
```flux
-- 单行函数
double x = x * 2

-- 多行函数
area shape =
  match shape
    Circle r      -> pi * r * r
    Rect w h      -> w * h
    Triangle b h  -> b * h / 2

-- 泛型 + 约束
first: List a -> Maybe a
first list =
  match list
    []     -> Nothing
    x :: _ -> Just x
```

---

## 三、招牌特性：流管道 `|>`

```flux
-- 数据从左向右流动
users
  |> filter (.age > 18)
  |> map .name
  |> sort
  |> take 10
  |> print

-- 流是惰性的，以上只遍历必要元素
```

### 双向管道 `<<|`（反向组合）
```flux
render <<| validate <<| parse <| input
```

---

## 四、类型系统

### 代数数据类型
```flux
type Tree a =
  | Leaf
  | Node (Tree a) a (Tree a)

type Result e a =
  | Ok a
  | Err e
```

### 效果系统（Effect Tracking）— Flux 的杀手锏

函数签名标注**它能做什么**，编译器强制检查：

```flux
-- 纯函数：无效果
add: Int -> Int -> Int

-- 带效果的函数
readFile: Path -> Text ! {IO, Throws FileError}
queryDb:  SQL  -> List Row ! {IO, Async}

-- 效果像类型一样被追踪和传播
process: Path -> Report ! {IO, Async}
process path =
  text  <- readFile path !        -- `!` 表示"解包效果"
  rows  <- queryDb (toSql text) !
  pure (summarize rows)
```

调用者必须处理效果，**不可能偷偷做 IO**。

---

## 五、无异常的错误处理

```flux
divide: Float -> Float -> Result Text Float
divide _ 0 = Err "除零"
divide a b = Ok (a / b)

-- `?` 操作符：Err 时提前返回，Ok 时解包
average xs =
  let n = toFloat (length xs)
  sum <- divide (total xs) n ?     -- 自动传播 Err
  pure sum
```

---

## 六、并发：轻如鸿毛的 `spawn`

```flux
-- 结构化并发，无回调地狱
main =
  parallel
    user    <- fetchUser id
    orders  <- fetchOrders id
    posts   <- fetchPosts id
  pure (Dashboard user orders posts)
-- 任一失败则全部取消，资源自动清理
```

---

## 七、模式匹配 + 守卫

```flux
describe n =
  match n
    0           -> "零"
    x | x < 0   -> "负数"
    x | x % 2 == 0 -> "正偶数"
    _           -> "正奇数"
```

---

## 八、记录与"透镜"访问

```flux
type User = { name: Text, age: Int, address: { city: Text } }

-- 不可变更新（深层）
alice2 = alice |> set (.address.city) "北京"

-- 部分应用字段访问
cities = users |> map (.address.city)
```

---

## 九、完整示例：单词频率统计

```flux
import File (readText)

topWords: Int -> Path -> List (Text, Int) ! {IO}
topWords n path =
  readText path !
    |> words
    |> map toLower
    |> group
    |> mapPairs length
    |> sortBy (desc snd)
    |> take n

main =
  match topWords 5 "book.txt" !
    Ok pairs -> pairs |> forEach print
    Err e    -> logError e
```

---

## 十、Flux 的独特之处总结

| 特性 | 说明 |
|------|------|
| **效果即类型** | `! {IO, Async}` 写在签名里，编译器强制 |
| **一切皆流** | 惰性、可组合、统一抽象 |
| **零异常** | `Result` + `?` 全覆盖 |
| **结构化并发** | `parallel` 块自动管理生命周期 |
| **全量类型推断** | 注解只为文档与契约 |
| **无 null** | `Maybe` 替代，编译期消灭空指针 |

---

想深入哪个部分？我可以继续设计：**模块系统**、**宏/元编程**、**与 C 的 FFI**、或者**写一个微型解释器原型**。
