# [rerun:space-bunny-free] 任务1 函数式编程语言 | 条件: baseline | 第 8 次

**Prompt:** 设计一个全新的函数式编程语言

**耗时:** 106.0s | **tokens:** 196/16000(推理 7976) | **finish:** length

---

# Iris —— 一种以「代数效应 + 线性能力」为核心的新型函数式语言

> 设计文档 v0.1 · 一句话概括：**Iris是一门强静态类型、严格求值、代数效应（Algebraic Effects）与模式匹配为一等公民、并且带线性（能力）类型系统的纯函数式语言**。副作用不是"逃逸口"，而是**类型签名的一部分**，由 handler 显式捕获与解释；可变资源不是"约定"，而是**由线性类型系统静态保证的不变量**。

---

## 目录

1. [设计目标与非目标](#1)
2. [语言概览卡片](#2)
3. [词法与语法](#3)
4. [核心语言构造](#4)
5. [类型系统](#5)
6. [效应系统与 Handler（核心特性）](#6)
7. [线性与能力类型（第二核心特性）](#7)
8. [模块、重载与命名](#8)
9. [宏、编译期求值与反射](#9)
10. [求值语义与运行时](#10)
11. [编译器管线](#11)
12. [标准库](#12)
13. [完整示例程序](#13)
14. [与现有语言对比](#14)
15. [实现难度、风险与路线图](#15)
16. [语法汇总（EBNF）](#16)

---

<a id="1"></a>
## 1. 设计目标与非目标

### 1.1 五条设计原则

| # | 原则 | 具体含义 |
|---|---|---|
| P1 | **一切皆表达式，一切效应皆类型** | `fn f : Int ->[IO, Stderr] Int`；签名里写不出来的副作用，编译器一定不让你写 |
| P2 | **可组合的错误/状态/并发** | 不是异常，不是回调，不是 Future/IO monad 的语法糖，而是可多路、深浅可选、可嵌套的 handler |
| P3 | **线性即安全（资源可推理）** | 文件、socket、锁、句柄默认线性；"能不能释放"是一个可以静态判定的问题 |
| P4 | **总函数优先，穷尽性强制** | 无未初始化变量、无隐式类型强制转换；模式匹配必须穷尽，effect 必须处理 |
| P5 | **双向类型检查 + 洞（holes）** | 上→下检查用于声明/洞，下→上检查用于表达式，兼顾推断力与引导式报错 |

### 1.2 明确的非目标

- ❌ 不做隐式类型转换（`0` 不是 `0.0`）、不做字符串到数字的自动解析。
- ❌ 不以异常作为默认控制流（`handle*` 可以完美模拟，但它只是普通构造）。
- ❌ 不做默认惰性（默认严格求值；惰性必须显式 `lazy`）。
- ❌ 不追求"零成本 handler"和"零成本抽象"的全部同时成立；Iris 追求**可预测的成本模型**（见 §10.4成本规则）。
- ❌ 不做全程序隐式多态特化（monomorphization 爆炸）；类型类用字典传递。

---

<a id="2"></a>
## 2. 语言概览卡片

|维度 | 选择 |
|---|---|
| 名字 | **Iris**（鸢尾 / 虹），口号：*"One program, many effects."* |
| 范式 | 纯函数式 + 代数效应 + 线性能力类型 |
| 类型检查 | 完全静态；HM核心 + 行多态 + 线性/仿射 + 可选 `dyn` 渐进边界 |
| 求值策略 | 严格（CBV），`lazy` 为按需调用（call-by-need，带 memoization） |
| 数据 | 代数数据类型、记录（元组/具名）、不可变、数组、闭包 |
| 控制流 | 表达式式：`match` / `if` / `case` / `let` / `shandle` / `for-in`（由 `Foreach` effect 反糖） |
| 并发 | 结构化（structured），由 `Concurrent` effect + channel 表达；`spawn`/`join` 必须作用域内 |
| 模块 | 具名模块、一等公民模块值、参数化模块（functor）、`open` 重载导入 |
| 编译期 | 卫生（hygienic）宏 + `const` 编译期求值 + `derive` |
| 运行时 | 可选的（可编到 LLVM，也可解释执行用于教学）；引用计数由线性类型推导 |
| 编译目标 | 自定义 SSA 中间表示 → LLVM IR → 原生码 |

---

<a id="3"></a>
## 3. 词法与语法

### 3.1 布局规则（Offside Rule）+ 显式双模Iris 默认**布局敏感**，同时允许 `do ... end` 显式块（便于与现有编辑器/生成代码互操作）。

```
val xs = do let a = 1
  let b = 2
  a + b
end
```

规则：缩进宽度由编译器维护一个"逻辑列"栈；`let`/`match`/`fn`/`do` 等引导块引入新层；空行被忽略（不重置列）；`in`/`end` 可显式闭合。**Tab宽度固定为 8 且视为不兼容输入（报错并给出建议）**——这是常见痛点，Iris 选择"吵闹地失败"。

### 3.2 词法元素

```
标识符      [A-Za-z_][A-Za-z0-9_']*        -- 允许 ' 作为续字符（不与单引号冲突）
小写标识符  foo → 值/函数大写标识符  Foo        → 构造器/类型构造器/模块/效应
运算符      + - * / % ^ = != < <= > >= <> ++ :: -> ->[e] | \ & := |> => ; , .
注释        -- 行注释 (-块注释，可嵌套 -)
字面量      42  0x1F  0b1010  3.14  1.0e-9  'a'  '\n'  "str"  "esc\u{1F600}"
            3r 3i 3u8            -- 无后缀 = Int；显式宽度后缀
            1.0f                 -- 单精度（Float 单独类型，默认 f64）
```

### 3.3 表达式优先级（从高到低）

```
λ \x.e          > 应用 f x >   ::构造 >   ->[e] 箭头 >   ^        >   * / %         >   + - ++   >   比较   >   |> 管道   >   :=赋值      >   ;序列   >   match/if/let/shandle/handle 分支
```

`|>` 反过来写：`x |> f` ≡ `f x`；`x |> f |> g` ≡ `g (f x)`。管道对 handler 友好（便于 `|> handle`）。

---

<a id="4"></a>
## 4. 核心语言构造

### 4.1 声明与签名

签名用**外部声明**风格（便于文档提取与 API 稳定性），也支持内联标注：

```iris
-- 外部声明形式（推荐用于导出 API）
inc : Int -> Int
inc x = x + 1

-- 内联标注形式（适合局部）
let y : Int = inc (1 + 2)
let z : Int? = inc 1                 -- 洞：?_ 类型，推断后回填
```

多子句函数与递归：

```iris
area :: Shape -> Float
area s = match s with
  Circle r          => math.pi * r * r
  Rect (w, h)       => w * h

length :: [a] -> Int
length = fn  | []        => 0
  | (x :: xs) => 1 + length xs
```

### 4.2 代数数据类型

```iris
type Option a = None | Some a

type Vec = { x :: Float, y :: Float }

type Tree a
  = Leaf
  | Node { left :: Tree a, value :: a, right :: Tree a }

type Shape = Circle Float | Rect { w :: Float, h :: Float }
```

- `type` 声明封闭类型（exhaustive matching 强制）；
- `class`/`open` 提供开放层次（见 §8）；
- 记录可用 `..` 开放行：`{ x :: Float, .. }` 表示"还有别的字段"。

### 4.3 模式匹配

```iris
describe :: Option (Tree Int) -> String
describe t = match t with
  None                     => "empty"
  Some Leaf                => "leaf"
  Some (Node { left, .. }) => "node"                -- 记录模式 + 忽略其余字段
  Some (Node { value =0 }) => "zero node"          -- 字段模式（类似 Swift）
  Some (Node l, v, r) if is_balanced l r => "balanced node"
  Some _                   => "some node"           -- 通配
```

高级模式一览：

| 模式 | 示例 | 语义 |
|---|---|---|
| 或模式 | `Some 0 \| Some 1 => ...` | 同绑定集才合法（Koka/Scala 风格） |
| 别名 | `n as m => ...` | `n` 是子模式，`m` 是整值 |
| 视图模式 | `Some x when_map f => ...` | 需 `view` 声明才允许（防滥用） |
| 切片 | `xs[1..3]` | 需要 `Slice a` 实例，显式代价 |
| 字面量范围 | `0 ..< 3` | 反糖成 `n if0 <= n < 3` |
| 位置参数 | `Node l, v, r` | 位置模式，与 `Node {left, value, right}` 等价 |

**穷尽性 + 冗余 + 线性**三重检查：编译器报错"非穷尽：缺少 `Some (Node Leaf, _, _)`"或"此子句永不可达"或"分支使用了已移动的值"。

### 4.4 `let` 模式、解构与影子

```iris
let (a, b) = pair -- 严格解构
let Point { x, y } = p     -- 记录解构
lazy tree = Node { left = tree, value = 1, right = Leaf }   -- 值递归（需 lazy）
```

### 4.5 管道与点投影

```iris
xs |> List.map inc |> List.filter (fun x => x > 2) |> List.sum
p.x -- 投影（也可作函数：p.x）
xs.len -- 需 `Length` 重载
```

---

<a id="5"></a>
## 5. 类型系统

### 5.1 种类系统（Sorts / Kinds）

```
Sort ::= Ty            --类型的类型 | Ef -- 效应的类型（effect row）
       | Row           -- 记录行
       | Mod t         -- 模块类型
```

举例：

```
Option : Ty -> Ty
List          : Ty -> Ty
State         : Ty -> Ef
{ x :: Float, y :: Float } : Row
Map K : Ty -> Ty
```

### 5.2 核心文法

```
τ ::= a | Int | Float | Bool | Unit | String | Bytes | dyn τ | τ τ₂.. (应用)
   | λ | ∀ a. τ | τ -> τ | (τ, τ) | { ℓ :: τ, .. } | Module τ
   | cap τ@ρ            -- 线性能力类型，ρ 为推断出的区域
ε ::= ⟨⟩ | ℓ τ, .. -- 效应行
```

函数类型携带效应行：

```
τ -> τ -- 语法糖：τ ->⟨⟩ τ （纯）
τ ->[ε] τ     -- 显式效应
τ ->[ε; f a] τ -- 效应 + 类型类约束
```

### 5.3行的多态与子类型记录行与效应行共用同一个行多态引擎（Leijen 式 row unification）。开放行用 `| r` 写：

```
type Store = { count :: Int, name :: String, ..r }

incCount :: { x :: Int, ..r } ->{ IO, ..r } { x :: Int, ..r }
incCount r = r { x = r.x + 1 }
```

**效应子类型（关键且反直觉的方向）**：

```
A ->[e] B  <:  A ->[e'] B 当且仅当   e ⊆ e'
```

即"更纯的函数可以用在允许更多副作用的位置"。这让 handler 实现**效应擦除**成为类型系统的自然推论：

```iris
runState :: ∀ a, S. (a ->[State S] a) -> S -> (a, S) -- 结果是纯的
runState init f = shandle f init with State {...}        -- State效应被 handler 消掉
```

### 5.4 重载 / 类型类

Iris 的重载是**字典传递的轻量类型类**（Haskell/OCaml 风格），并允许 `open` 把方法引入作用域（Rust/Swift 风格）：

```iris
class Eq a where
  sig (==) :: a -> a -> Bool

instance Eq Int where
  (==) a b = int_eq a b

instance [Eq a, Eq b] Eq (a, b) where
  (==) (a₁, a₂) (b₁, b₂) = a₁ == b₁ && a₂ == b₂
```

- `==` 无歧义时直接用；
- `a == b` 与 `open Eq` 冲突时以作用域最近者为准（类似 Swift）；
- **一致性（coherence）检查**：不允许重叠实例，除非标注 `[overlap]`（仅在定义它的模块内可见）；
- 类型类约束与效应一起出现在签名：`sig sort ::[ Ord a ] [a] -> [a]`。

### 5.5 渐进类型边界

```iris
read_any :: Bytes -> dyn Value -- 存在一个动态类型擦除点
serialize :: Value ->[ IO ] Bytes
```

- `dyn τ` 是一个**单射（injective）擦除**，跨越它的调用不参与类型推断；
- `dyn` 边界的效应会被**求并集**（conservative effect inference），不会丢信息；
- 动态层无 GC 暂停、无装箱分配开销的主要部分（表示与静态层相同）。

---

<a id="6"></a>
## 6. 效应系统与 Handler（核心特性）

### 6.1 效应声明

效应是**带签名的一族操作**，可以参数化，并且操作结果类型可多态（用于 `abort` 这类"逃逸"操作）：

```iris
effect State S where
  sig get :: Unit -> S
  sig put :: S -> Unit

effect Fail E where
  sig abort :: E -> a          -- 'a 是全称量化的：abort 的结果类型可以是任意 a

effect Log where
  sig emit :: String -> Unit

effect Concurrent where
  sig spawn :: (Unit ->[ ?e ] a) -> Thread a      -- 'e 被 effect-polymorphism 捕获
  sig join :: Thread a -> a
```

一个函数的效果类型就是它**可能执行的效应操作行的并集**：

```iris
transfer ::[ State Int ] () -> ()
transfer = do
  let v = get ()
  put (v * 2)
  log "moved"                       -- 推断出 {State Int, Log}
```

签名可以手工写（也可完全省略让编译器推断）：

```iris
transfer :: () ->[ State Int, Log ] ()
```

### 6.2 Handler：语法与三种形态

```
handle  e with { c₁ ; ... ; cₙ }                  :: A -- 深（multi-shot）
shandle e with { c₁ ; ... ; cₙ }                  :: A         -- 浅（one-shot，线性消费 resume）
shandle e as slot :: S with { ... }                :: (A, S)    -- 带状态槽
handle* e with { ... }                             :: Unit      -- 中止式（可模拟异常/提前返回）
```

子句形式：

```
op pats => body -- body :: A，可用 resume r（多态于操作的结果类型）
op pats => resume r with s'        -- 在继续前把状态槽设为 s'
op pats => let a = resume r in ... --显式绑定续延结果
```

### 6.3 语义（简明的自然语义）

给定计算 `e :: A`（其效应行为 `e₀`），效应操作集 `H`，条款 `cl(op)`。

**深 handler（多路）**：

```
⟦ handle e with {cl} ⟧ ρ κ =  fold_ops(⟦e⟧, e)
  fold_ops(pure a)          = κ a
  fold_ops(op(args) ⟨k⟩)    = ⟦ cl(op) (args) [ k ] ⟧        -- k 在多路下可被多次调用
```

**浅 handler（单路）**：条款中 `resume` 至多被调用一次，且**必须恰好消费一次**（否则由线性规则报错"续延泄漏/未使用"）。运行结束返回 `(a, slot)`。

**状态槽**：`shandle e as slot :: S` 中，槽变量在每一步操作前可见为 `slot`；`resume r with s'` 在继续前把槽置为 `s'`；整体结果为 `(最终值, 最终槽)`。**无 resume 调用时**，handler 在该点提前返回条款值与当前槽。

### 6.4 一组完整例子**(1) State：深 handler 不够用 ⇒ 浅 handler**

```iris
eval :: Expr ->[ State Env ] Value
eval e = match e with
  Num n => Val n
  Var x        => get_env x                 -- get_env = get () then lookup
  Plus (a, b)  => Val (eval a.value + eval b.value)

run :: Expr -> Env -> (Value, Env)
run e env = shandle eval e as env with State where
  get () => resume env
  put s  => resume () with s
```

注意 `eval` 的类型里只有 `State Env`——**它无法访问 IO，也无法发明新的效应**。

**(2) Fail：可恢复错误（深 handler 做列表收集）**

```iris
effect Fail E where
  sig abort :: E -> a

collect :: (() ->[ Fail E ] a) -> [Result a E]
collect c = handle c with Fail where
  abort e => Cons (Error e, resume any)      -- 多路：收集所有失败
```

**(3) 中止式：`handle*` 变成 try/catch**

```iris
attempt :: (() ->[ Fail E ] a) -> Result a E
attempt c = shandle* c with Fail where
  abort e => Error e                          -- 不 resume ⇒ 提前结束
```

**(4) 纯 handler：非确定性 / 状态无关的组合**

```iris
effect Choose where
  sig choose :: Bool -> a

all :: (() ->[ Choose ] a) -> [a]
all c = handle c with Choose where
  choose _ => Cons (resume true, resume false)
```

**(5) 双向消除、嵌套与组合**

```iris
safe :: (() ->[ IO, Fail E ] a) -> Result a E
safe c = attempt (fn () => handle c with IO where
 op f => fn k -> fun st -> (k (apply f st) st, st)   -- IO 深处多路
          ret a    => fn _ -> fun st -> (a, st))
```

Iris 的 handler 是**普通表达式**：可以接受函数参数、返回 handler、存进数据结构、组合成高阶抽象。语法关键字 `handle` 只是 `shandle_fun` 的轻量反糖。

---

<a id="7"></a>
## 7. 线性与能力类型（第二核心特性）

### 7.1 想法

OCaml/Haskell 的 `Fd` 是"约定"，Rust 的 `File` 是"借用检查器"。Iris 走第三条：**纯函数式 + 一次性资源**。

```iris
type Socket = cap socket_handle@ρtype Db     = cap db_conn@ρ

type Handle a where
  sig acquire :: String ->[ IO ] (Handle a, a)
  sig release :: Handle a ->[ IO ] Unit
```

- `cap τ@ρ`：`ρ` 是**区域（region）**，由区域推断自动推导（默认不写）；
- 区域内**仿射（affine）**：可以使用、可以移动，但**不允许复制/隐式丢弃**（未用即报错，除非 `discard`）；
- 跨区域使用需要显式 `erase`（降级为 `dyn` 或转成拥有所有权的形式）。

### 7.2 效果

```iris
main :: () ->[ IO, Concurrent ] ()
main = do
  let (h, port) = acquire_handle "server.log"
  let thread = spawn (fn () => worker h port)     -- h 被移动进线程：合法
  join thread
  release h                                        -- h 已被移动，此处报错
```

编译器**拒绝**编译这段程序，并给出"值 `h` 在第 2 行已被移动"——因为这正是并发下最难查的一类 bug。

### 7.3 与运行时/GC 的关系

线性区域分析天然产出**引用计数插桩位置**：移动 = 计数转移，作用域结束 = 计数减到 0 ⇒ 析构回调（打开文件、关闭 socket、unlock）。于是：

- Iris 的默认运行时 = **精确引用计数 + 线性区域的 drop glue**，无 GC 停顿；
- 需要循环时用 `Weak` 显式构造弱环（对照：Rust 的 Rc 环泄漏问题被显式化而非静默）；
- 反过来，`lazy` 构造的 thunk环由编译器检测并要求 `lazy` 必须是"良构"的（thunk 图无环，编译器用区域+偏序检查）。

### 7.4 与 effect 的统一视角

**"拥有资源"是效应，"消耗资源"是线性。** Iris 把这两者统一为一个概念：*effect 是资源的使用，handler 是资源环境的求值器。* 例如 `State S` 本身就是"拥有一个 S 的线性状态线程"，所以必须用**浅** handler；而 `Log` 是"可复制的累加器"，用深 handler 更自然。

---

<a id="8"></a>
## 8. 模块、重载与命名

### 8.1 模块```iris
module Map (K : Ord K) -> Map K = struct        -- 参数化模块（functor）
  type t k = Empty | Bin { size :: Int, key :: k, val :: _, sub :: t k }
  sig empty :: t k
  sig insert :: k -> v -> t k -> t k
  sig to_list :: t k -> [(k, v)]
  ...
end

val IntMap : Ord K => Module (Map K)
```

- 模块类型即一阶值：`module_of(Map) @ Int` 是一等公民，能传参、返回、存进数据结构；
- `open Map` 只把 `sig` 中的名字引入当前作用域（不引入实现细节）。

### 8.2 类与开放层次（扩展代数数据类型）

```iris
class Show a where
  sig show :: a -> String

class Show a => Pretty a where               -- 超类约束
  sig pretty :: a -> String```

开放类型的实例化（扩展已有类型）用 `extend`：

```iris
extend List a where
  sig (++) :: [a] -> [a] -> [a]           -- 只能加方法，不能加字段
```

字段扩展用"包装类型 + 强制构造"模式（`newtype` + `extend`），保证没有 layout 不一致问题。

---

<a id="9"></a>
## 9. 宏、编译期求值与反射

### 9.1 卫生宏（hygienic）+ 卫生 quote/unquote

```iris
syntax unless c t = do quote
  if unquote(c) then () else unquote(t)

unless (x > 0) do
  print "must be positive"
```

- `quote ... unquote ...` 是**编译期解释器**求值的程序，类型被检查；
- 卫生（syntax contexts）由构造器名字 + 绑定解析栈实现，用户无法意外捕获/被捕获；
- 宏可以是**阶段化（staged）**的：一个宏生成的代码可以再展开宏。

### 9.2 编译期计算```iris
const primes : [Int] = do
  let sieve = fn n -> ...
  sieve 100

const size_of_page : Int = struct Json.encode schema_page |> Bytes.len
```

编译期求值与"编译期断言"：

```iris
const assert_all_effects_declared : Unit =
  const (fn () => ()) : () ->[ ??? ] ()     -- 若结果类型含未知效应 ⇒ 编译失败
```

### 9.3 派生与反射

```iris
derive [Show, Eq] for Tree a where [Show a]

case_syntax { -- 把语法层暴露为数据（.reflect）
  syntax_name = "case_syntax"
  syntax_arity = 2
}
```

`reflect` 提供结构化的语法反射（比文本 quote 更可控），用于编写格式化器、重写器、lint 工具。

---

<a id="10"></a>
## 10. 求值语义与运行时

### 10.1 核心语义（基于 continuation 的效应消除）

Iris 的求值器采用**带续延的运算语义**，这是代数效应实现的经典选择：

```
( V, κ )                              -- 值
( Op(op, args, k) , κ )               -- 待决操作
( F(f, env) , κ )                     -- 函数闭包

step (V, κ)                    = (κ V)
step (Op(op, args, k), κ)      = 查 handler 表 ⇒ 条款 (cl, henv)
                                 cl 环境中注入 resume = λr. 继续 (k r)
                                 若 clause 返回值 v 且调用了 resume ⇒ (v, κ)
                                 若未调用 resume ⇒ (v, κ)  [提前返回/abort]
```

- 深 handler：条款里的 `resume` 可被多次调用 ⇒ 需要**续延的深拷贝/多路表示**；
- 浅 handler：`resume` 只被消费一次 ⇒ 表示为一个**一格（one-shot）续延对象**，几乎零成本；
- 编译器对 `shandle` 做**去功能化（defunctionalization）**，把续延表示成跳转表 + 帧栈，浅 handler 消除后基本退化为普通 CPS/异常机制。

### 10.2 尾调用与空间安全

- 语言保证**尾调用优化**：编译器把 `fn` 编译为尾位置跳转（trampoline-free，LLVM `musttail`）；
- 极值化递归（如斐波那契）可写栈安全的非尾递归，编译为循环；
- 无隐式栈增长（无 `eval`、无宏展开出无限代码）。

### 10.3 运行时数据布局

```
V ::= i64 | f64 | bool | ptr | (tag, ptr...) | closure(cptr, env)
值表示：NaN-boxing（小值类型）+ 可选装箱；bigint/字符串/数组为堆对象
堆对象：header { tag, size, rc, weak_refs } | payload
```

- **引用计数**由线性/区域分析插桩；`lazy` thunk 环由区域+偏序检查排除；
- 提供 tracing GC 作为**可选后端**（`--gc=tracing`），用于无法静态证明线性的边界（`dyn`/FFI）；
- 运行时还提供：一个**可解释执行模式**（教学/调试用），一个效应感知的调试器（见 §11.4）。

### 10.4 成本规则（可预测性）

| 构造 | 静态已知成本 |
|---|---|
| 纯函数调用 | O(1)，闭包 ≤ 若干寄存器 |
| 记录/构造器分配 | 精确的堆分配计数 |
| `shandle` | 一次栈帧 push（≈ 1 个闭包），退出可被循环不变式消除 |
| `handle`（深） | **不隐式复制续延**；若续延未被多次 resume，编译器证明后降级为浅实现（`handle!`） |
| 线性 drop | 编译期插入，无隐藏析构 |
| `dyn` 调用 | 一次间接调用 + 表示检查 |

---

<a id="11"></a>
## 11. 编译器管线

```
源文件
  │① 词法（含布局分析）
  │  ② 解析 → AST（带精确 source span + syntax context）
  │  ③ 宏展开（编译期解释器、卫生重命名）
  │  ④名称解析（模块/functor 实例化、open、类型类约束收集）
  │  ⑤ 双向类型检查（区域 + 效应 + 线性）+ 模式穷尽性检查 + 告警（未用变量等）
  ▼
Typed Core（高阶、脱糖：let*/match→case、管道、handler→函数）
  │  ⑥ 去功能化续延 → 效应中间表示 ECore
  │  ⑦ SSA 构造（br_mem2reg、egraph 重写）→ 优化
  │  ⑧ 闭包转换、装箱/拆箱、逃逸分析、线性 drop glue 插桩
  ▼
LLVM IR → 原生码```

**关键实现策略**

1. **类型检查是模块化的**：行多态用 Rémy 风格的行合一；效应推断是"操作标签的并集 + handler 处的差集"，可以做成一个近线性的一遍推断；线性检查与类型检查并行（同一 AST 上不同属性），区域推断用标准的约束生成 + 合一 + SCC。
2. **handler 形状去特化**：浅 handler 在每个 site 生成一个 1..n 字节的 tag + 跳转表；深 handler 若静态证明单次 resume，降级为浅。
3. **线性 → refcount**：把"移动"编译为指针转移，把"作用域结束"编译为 `dec + branch-to-dtor`；配合 LLVM 的 `sroa`/`instcombine` 消除常见冗余。
4. **互操作**：`extern "C" fn`、C 结构体布局标注 `[repr(C)]`、Rust-like 的 `#[no_mangle]`；FFI 引入的效应在注解中显式声明（FFI 不许偷偷产生未声明效应）。

### 调试与工具链（不是事后补的）

- 编译器内部保存**完整 elaboration term**，错误信息直接用 AST 打印（比如"你写了 `List.map`，但这里是 `Array`"）；
- **洞驱动 IDE**：所有未解析标识符都是可点击的洞，能推导并给出候选插入；
- **效应感知调试器**：程序跑在一个效应解释循环里，可以在 handler 边界单步（"这次 IO 被谁处理了？"直接可见）；
- **回溯调试（time travel）**：记录一次运行中的效应轨迹（如 IO 调用），当出现异常时用**另一个 handler 解释同一轨迹**重放 ⇒ 得到完全不同的输出。这是 Iris 独有的调试能力。

---

<a id="12"></a>
## 12. 标准库（`Std`）

| 模块 | 内容 |
|---|---|
| `Prelude` | 基本函数、默认 `open` 的类型类 |
| `Option` / `Result` / `Either` | 组合子齐全，`do` 记法由 handler 反糖 |
| `List` / `Array` / `Seq` / `Vec` | 三种容器（持久/定长/可增长） |
| `Map` / `Set` | 参数化模块，需 `Ord` |
| `Text` | UTF-8 感知，切片 O(1)（rope） |
| `IO` | 效应类型 + 常用操作 |
| `File` / `Net` / `Process` | 基于 `cap` 线性句柄 |
| `Concurrent` | `Thread`、有/无缓冲 channel、屏障、任务组（作用域结束时自动 join） |
| `Time` / `Random` / `Crypto` | 均为 `IO` 效应操作 |
| `Json` | 用 handler 实现的组合式解析器（见 §13.3） |
| `Fmt` / `Show` / `Debug` / `Pretty` | 格式化与漂亮打印 |
| `Test` | 基于效应捕获（记录断言）的测试框架 |
| `Iter` | 惰性 + `Fuse`（可提前终止的迭代器） |

### `do` 记法只是 handler 的语法糖

```iris
main :: () ->[ IO ] Unit
main = do
  line <- read_line ()                  -- 编译为 Result 反糖 + Fail handler
  when (line != "") do
    print (upper line)
```

编译器把它脱糖成 `shandle*` + `Fail String` handler，因此 `do` 块可以自由嵌套在任意效应上下文中。

---

<a id="13"></a>
## 13. 完整示例程序

### 13.1 状态机：带 handler 的 HTTP 请求重试

```iris
effect Http where
  sig request :: Url ->[ Http ] Response sig retry :: Int ->[ Http ] () -- 最多重试 n 次

effect Fail E where
  sig abort :: E -> a

-- 纯逻辑：不知道 IO、不知道 Http 存在
fetch_with_retry :: Url ->[ Http, Fail NetErr ] Response
fetch_with_retry url = do
  let attempt0 = abort NetErr_Timeout
  let attempt n = do
    let r = request url
    if r.status == 200 then r
    else do retry n; attempt (n - 1)
  attempt 3

-- 环境：注入策略（测试时可替换为假实现）
main :: () ->[ IO ] Unit
main = do
  let result = shandle fetch_with_retry "https://example.com" as env with Http where
      request url = do
        log ("GET " ++ url)
        if url == "https://example.com" then Ok Response_200
        else Ok Response_500
      retry n     = log ("retry " ++ show n)
  attempt (fn () => handle result with IO where
    op f = fn k -> fun st -> (k (apply f st) st, st))
  print (show result)
```

- `fetch_with_retry` 是**纯类型**的安全代码，测试时只需换一个 `Http` handler；
- `attempt` 让 `Fail` 变成 `Result`，再由 `shandle*`（而非 try/catch）实现；
- `Http` handler 可以嵌套在别的 handler 内（如测试框架用深 handler 同时跑100 个不同输入）。

### 13.2 线性能力 + 结构化并发：worker pool

```iris
type Conn = cap conn@ρ

type Task = { run :: (() ->[ ?e ] Unit), deadline :: Instant }

-- 并发被限制在任务组的效应内：不可能泄漏线程
pool :: Conn -> [Task] ->[ Concurrent, IO ] ()
pool conn tasks = task_group do
  chan <- channel (len tasks)
  for t in tasks do
    spawn (fn () =>
      chan.send (run_one conn t.run)          -- 结果回传；异常变成 tagged value
    )
  for _ in tasks do
    let outcome = chan.recv ()
    log (describe outcome)
```

要点：
- `chan` 是线性能力，只能被 `task_group` 作用域内的任务持有；
- `task_group` 退出时若某子任务未 join ⇒ **运行时异常**（不可能静默丢线程）；
- `?e` 效应多态让 `spawn` 与子任务效应无关（无 monad transformer 的地狱）。

### 13.3 用深 handler 写组合式 JSON 解析器

```iris
effect Parse where
  sig input :: Bytes ->[ Parse ] ()
  sig fail :: ParseErr -> a

-- Parser 是"消费输入"的 CPS 计算parser_combinator :: (() ->[ Parse ] a) ->[ Parse ] a -> (() ->[ Parse ] a) -> (() ->[ Parse ] a)
parser_combinator p q alt = do
  with_backtrack (alt<|> do
