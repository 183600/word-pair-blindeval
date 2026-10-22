# [v2:deepseek-flash] 任务1 函数式编程语言 | 条件: baseline | 第 8 次

**Prompt:** 设计一个全新的函数式编程语言

**耗时:** 70.12s | tokens: 37/12800

---

# 澄 (Chéng) — 一门以"能力"为唯一上下文机制的函数式语言

> 澄：水静而清。取此名因为它想做的事：把函数式语言里那些散落的隐式机制，澄清成同一种东西。

---

## 一、三条设计信条

**1. 凡是"从上下文隐式得到的东西"，都走同一条路径。**
打印的能力、读取时钟的权限、`Show a` 的字典、随机数发生器的状态、一个 `Monad` 实例——在澄里它们是**同一个概念**：能力（ability），声明在函数类型的效应行里，由处理器（handler）提供。语言里没有"类型类 / 隐式参数 / effect / monad"这样四个分开的机制。

**2. 处理器是数据。**
处理能力的值，与 `Int`、`List a` 地位相同：可传参、可返回、可组合、可被另一个处理器观察。程序的运行期就是一个处理器栈，没有别的黑箱。

**3. 编译期不是特区。**
程序是可以被当作值检视、改写、部分求值的数据。宏、常量折叠、特化、代码生成，用的都是 `Code a` 这一种类型和"应用处理器"这一个原语。语言本身不规定哪一步必须发生在编译期。

---

## 二、语法总览

```cheng
-- 函数：无关键字，参数空格分隔，自动柯里化
inc   x   = x + 1
add   x y = x + y

-- 类型标注用冒号（:: 留给 cons）
inc : Int -> Int

-- case 用 | 分支
map f xs = case xs of
  | []       -> []
  | x :: xs' -> f x :: map f xs'

-- 记录：结构化、匿名字段名
point  = { x = 1, y = 2 }
origin = point.{ x = 0 }          -- 函数式更新

-- 管道与组合
result = [1, 2, 3]
  |> map inc
  |> filter (> 2)

-- 递归用 let rec
let rec fact n = if n == 0 then 1 else n * fact (n - 1)
```

---

## 三、类型系统

### 基础类型

`Int` `Float` `String` `Char` `Bool` `()`，加上 `List a`、`Maybe a`、`Result e a` 等标准 ADT：

```cheng
data Maybe a    = None | Some a
data Result e a = Err e | Ok a
data Tree a     = Leaf | Node (Tree a) a (Tree a)
```

### 行多态记录

记录是结构化的、匿名的，宽度用行变量表示：

```cheng
getX : { x: Int | r } -> Int
getX p = p.x

-- 就地扩展
setX : { x: Int | r } -> Int -> { x: Int | r }
setX p v = p.{ x = v }
```

### 效应行

任何函数类型都带一个**效应行**，写在 `->` 右侧：

```cheng
pureAdd : Int -> Int -> Int          -- 默认是空行 < >
main    : () -> <Console, Clock> ()
```

`=>` 语法是行约束的糖：

```cheng
render : Show a => a -> String
-- 等价于 render : a -> <Show a> String
```

### 惰性

默认严格求值。需要惰性时显式标注：

```cheng
data Lazy a = ...
delay : (() -> a) -> Lazy a
force : Lazy a -> a

naturals : Lazy (List Int)
naturals = delay (\() -> 0 :: force (delay (\() -> ...)))
```

严格求值换来的是**处理器语义的可预测性**：`resume` 交还控制权的时机是可以从代码读出来的。

---

## 四、能力（Ability）——统一的上下文

### 声明

```cheng
ability Console =
  | print    : String -> ()
  | readLine : () -> String

ability Show a =
  | show : a -> String

ability Random =
  | randomInt : (lo: Int, hi: Int) -> Int

ability State s =
  | get : () -> s
  | set : s -> ()
```

### 提供能力

提供能力的东西就是**处理器**：

```cheng
console : Handler Console
console = handler
  | print s    -> primIO (writeStdout s) >> resume ()
  | readLine () -> resume "anon"
```

### 使用能力

```cheng
greet : <Console> () -> ()
greet = do
  print "你的名字？"
  name <- readLine ()
  print ("你好，" ++ name)

main = handle greet () with console
```

`handle expr with h` 把 `expr` 里所有 `Console` 操作交给 `h` 处理。

### 关键的统一：类型类就是能力

```cheng
-- 不需要 typeclass 关键字
ability Show a = | show : a -> String

render : Show a => a -> String
render x = "[" ++ show x ++ "]"

-- 提供一份实例，就是提供一个处理器
showInt : Handler (Show Int)
showInt = handler
  | show n -> resume (intToString n)
```

调用 `render 42` 时，编译器从当前处理器栈里解析 `Show Int`，相当于 Haskell 的字典传递——但机制只有一套，语法也只有一套。`Monad` 同理：

```cheng
ability Monad m =
  | pure  : a -> m a
  | bind  : m a -> (a -> m b) -> m b
```

### 组合处理器

处理器是值，所以它们可以像普通数据一样组合：

```cheng
-- 叠加：右边处理左边不认识的
stack : Handler a -> Handler b -> Handler (a, b)

main = handle greet () with stack console clock
```

---

## 五、资源：线性能力

普通能力是**幂等**的（可以反复提供、反复调用）。资源是**仿射 + 关闭义务**的：

```cheng
resource File =
  | read  : () -> String
  | write : String -> ()
  | close : () -> ()      -- 必须被调用一次
```

`resource` 的语义是：**提供该能力的处理器作用域内，`close` 必须在所有控制流路径上被调用恰好一次，且能力操作不能逃逸到作用域外。**

```cheng
cat : Path -> <File> String
cat p = do
  s <- read ()
  close ()
  pure s
  -- 若漏掉 close()，编译期报错：
  --   error: resource `File` not closed on all paths
```

这把 RAII、`using`、`try/finally`、`bracket` 收敛成一个类型检查的规则。

---

## 六、处理器语义

处理器分支体里暴露一个原语 `resume`：

- `resume v` —— 把 `v` 作为该操作的结果交回续延，控制权回到 `handle` 块；
- `resume v with s` —— 同上，并把处理器的**新状态**设为 `s`（用于 `State` 这类由处理器自身携带状态的场景）。

```cheng
stateHandler : s -> Handler (State s)
stateHandler init = handler
  | get ()  -> resume init with init
  | set s   -> resume ()   with s

-- get 返回当前状态，状态不变；set 返回 ()，状态更新
test = handle do
    x <- get ()
    set (x + 1)
    get ()
  with stateHandler 0
-- test == 1
```

**深处理器**（deep handler）：续延包含 `handle` 块中剩余的所有效应。这是默认语义，因为它在大多数场景下更符合直觉。

---

## 七、编译期求值

不引入 `macro` 关键字、不引入 `quote`/`unquote` 语法糖。只有两条原语：

```cheng
-- 把一段程序冻结成值
quote : a -> Code a

-- 在编译期把一段 Code 展开成它代表的值
splice : Code a -> a     -- 只能在阶段 0 调用
```

再给处理器加一个阶段标注：

```cheng
@phase 0
handler ConstFold = handler
  | eval e -> resume (normalize e)
```

于是"在编译期求值一段代码"= "把阶段 0 的处理器作用上去"：

```cheng
-- 编译期常量折叠
N : Int
N = splice (quote (1 + 2 * 3 + 4))     -- 编译期就算出 10，运行期无开销

-- 编译期特化
@phase 0
handler Specialize = ...

@phase 0
def compilePipeline (p : Code Pipeline) : Code Pipeline
  = handle p with Specialize
```

**为什么这是设计信条 3 的具体化：**
- 运行期做的事 = 处理器处理请求树；
- 编译期做的事 = 同一台机器，只是处理器标了 `@phase 0`；
- `splice` 必须在编译期被消除，这是唯一的"阶段检查"。

语言本身不规定哪些计算必须在编译期完成——编译器可以因为折叠不划算而跳过，也可以因为对某段代码有信心而多做一点。宏、内联、特化、常量传播是同一个操作的不同参数。

---

## 八、完整示例：带撤销的计算器

```cheng
ability Console =
  | print    : String -> ()
  | readLine : () -> String

ability State s =
  | get : () -> s
  | set : s -> ()

-- 每一步都可以撤销：把状态的历史压栈
historyHandler : s -> Handler (State (s, List s))
historyHandler init = handler
  | get () ->
      resume (init.0) with (init.0, init.1)
  | set s ->
      resume () with (s, init.0 :: init.1)

undoHandler : Handler (State (s, List s))
undoHandler = handler
  | get ()  -> resume (???)  -- 读取栈顶
  | set s   -> ...

-- 提示语
prompt : <Console> () -> ()
prompt = do
  print "> "
  line <- readLine ()
  case line of
    | "undo" -> print "(略)"
    | _      -> print ("你说：" ++ line)

main = handle
    do
      prompt ()
      prompt ()
  with stack console undoHandler
```

（示例里 `???` 处略去具体状态读写细节；重点是：撤销、状态、输入输出三者都是**普通处理器**，可以自由叠加，没有任何一个需要语言开洞。）

---

## 九、关键的取舍

| 决策 | 好处 | 代价 |
|---|---|---|
| 能力 = 类型类 = 字典 | 只有一套机制要学、一套机制要实现 | 纯函数与"需要上下文"的边界变模糊；`show x` 也必须让 `Show` 出现在签名里 |
| 处理器是深处理器 | 中间状态干净，符合直觉 | 续延捕获整块，实现上要用 CPS 或分段栈 |
| 默认严格求值 | 处理器语义可以从源码读出 | 定义递归数据结构要显式 `Lazy` |
| `splice` 只在阶段 0 | 阶段检查简单 | 多阶段编程（MetaOCaml 式）的表达力受限 |
| 记录结构化、无 nominal 模块 | 组合方便、鸭子类型直觉 | 命名冲突、文档发现性稍差；用 `export` 约定缓解 |
| 资源靠"关闭义务"而非完整线性类型 | 实用、与现有代码兼容 | 比真线性类型弱：无法追踪部分移动 |

---

## 十、实现路线（建议）

1. **内核（Rust 实现）**：CPS + 分段栈的 effect handler 运行时，约 4–6k 行。
2. **类型检查**：行多态用 `row` 变量统一，能力解析用简单的"最近处理器优先"策略。
3. **前端**：手写递归下降，因为语法刻意做得小（函数定义 + `case` + 记录 + `do` + `handle`）。
4. **自举**：先用 Rust 写解释器，再用澄重写解释器，验证 `Code` + 处理器堆栈表达力足够。
5. **标准库**：`List`/`Map`/`String` 用普通函数；`Show`/`Eq`/`Ord`/`Foldable` 全部用能力声明；`File`/`Socket`/`Time` 用 `resource`。

---

## 一句话总结

**澄**的赌注是：函数式语言里那些看起来不同的隐式机制——类型类、效应、资源、编译期宏——本来就是同一件事的四种投影，而把这四者合并成"能力 + 处理器 + `Code`"，能让语言在概念上更小、在组合上更强。
