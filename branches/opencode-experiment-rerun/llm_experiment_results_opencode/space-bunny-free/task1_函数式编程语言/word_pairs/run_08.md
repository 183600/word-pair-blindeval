# [rerun:space-bunny-free] 任务1 函数式编程语言 | 条件: word_pairs | 第 8 次

**Prompt:** 在回答前面输出200组词，每组有两个词，从这些词获得灵感
设计一个全新的函数式编程语言

**耗时:** 161.4s | **tokens:** 213/15458(推理 8568) | **finish:** stop

---

# 一、200 组词（灵感素材库）

**A. 纯粹性核心**
```
001 惰性 · 递归        011 闭包 · 环境
002 代数 · 类型        012 可达性 · 回收
003 代数 · 效应        013 引用计数 · 循环
004 尾调用 · 栈        014 行多态 · 记录
005 单子 · 幺半群      015 逆变 · 直通
006 函子 · 适用        016 参数多态 · 秩
007 不动点 · 递归      017 类型类 · 实例
008 记忆化 · 纯度      018 穷尽 · 检查
009 柯里化 · 部分应用  019 空指针 · 黑洞
010 高阶 · 组合        020 选项 · 缺失
```

**B. 错误与资源**
```
021 结果 · 错误        031 穷举 · 证明
022 事务 · 回滚        032 定理 · 助手
023 原子 · 提交        033 模糊 · 测试
024 线性 · 资源        034 属性 · 测试
025 沙漏 · 归还        035 恢复 · 策略
026 缓冲 · 背压        036 降级 · 兜底
027 幂等 · 重试        037 空类型 · 底
028 校验 · 和          038 单位 · 乘法
029 契约 · 违反        039 真空 · 零
030 不变量 · 保持      040 底 · 单元
```

**C. 效应与并发**
```
041 效应 · 行          051 结构化 · 并发
042 句柄 · 深浅        052 信使 · 消息
043 遮蔽 · 提升        053 邮箱 · 队列
044 效应 · 多态        054 并发 · 交错
045 洋葱 · 分层        055 确定性 · 重放
046 回溯 · 剪枝        056 日志 · 重放
047 解析 · 组合子      057 事件溯源 · 快照
048 状态 · 单子        058 超时 · 取消
049 单子 · 变换        059 中断 · 信号
050 副作用 · 标注      060 工作窃取 · 调度
```

**D. 类型形状**
```
061 积类型 · 笛卡尔    071 隐式 · 参数
062 和类型 · 或        072 强制 · 转换
063 变型 · 逆          073 渐进 · 类型
064 变型 · 协变        074 动态 · 安全
065 参数多态 · 特化    075 向下转型 · 向上转型
066 种类 · 多态        076 双向 · 检查
067 种类 · 推断        077 索引 · 类型
068 抽象 · 类型        078 递归类型 · μ
069 接口 · 字典        079 递归类型 · ν
070 实例 · 见证        080 范畴 · 直觉
```

**E. 运行时与数据**
```
081 需求 · 严格        091 区域 · 推断
082 thunk · 强制       092 移动 · 语义
083 惰性 · 列表        093 复制 · 语义
084 列表 · 推导        094 内联 · 展开
085 引用 · 共享        095 尾位置 · 循环
086 不可变 · 历史      096 SSA · 寄存器
087 垃圾 · 标记        097 常量 · 折叠
088 分代 · 假说        098 类型 · 擦除
089 逃逸 · 分析        099 装箱 · 拆箱
090 所有权 · 借用      100 缓存 · 行
```

**F. 编译与优化**
```
101 虚表 · 去虚化      111 增量 · 编译
102 分派 · 缓存        112 依赖图 · 排序
103 泛型 · 字典        113 诊断 · 反例
104 谓词 · 专门化      114 错误消息 · 位置
105 边界 · 检查        115 布局 · 缩进
106 解释 · 编译        116 注释 · 文档
107 字节码 · 寄存器    117 引号 · 模板
108 JIT · 即时         118 卫生 · 作用域
109 预编译 · 启动      119 展开 · 归约
110 层级 · 编译        120 归约 · 机器
```

**G. 语法与模块**
```
121 语法 · 糖          131 区间 · 模式
122 模块 · 命名空间    132 守卫 · 条件
123 可见性 · 私有      133 块 · 表达式
124 封装 · 边界        134 管道 · 传递
125 沙盒 · 权限        135 反管道 · 注入
126 关键字 · 保留      136 命名 · 参数
127 标识符 · 撇号      137 可选 · 参数
128 字面量 · 枚举      138 模式 · 别名
129 解构 · 构造        139 版本 · 兼容
130 视图 · 模式        140 弃用 · 迁移
```

**H. 内存与硬件**
```
141 指针 · 对齐        151 内存 · 布局
142 伪共享 · 缓存      152 帧 · 布局
143 无锁 · 并发        153 闭包 · 逃逸
144 CAS · 循环         154 标签 · 跳转
145 原子 · 指令        155 二义性 · 括号
146 内存序 · 屏障      156 结合性 · 优先级
147 绿色 · 线程        157 优先级 · 层次
148 纤程 · 协作        158 数字 · 溢出
149 select · 超时      159 整数 · 任意精度
150 通道 · 阻塞        160 浮点 · 误差
```

**I. 工程与生态**
```
161 定点 · 十进制      171 追踪 · 调用栈
162 字符 · 编码        172 剖析 · 采样
163 字符串 · 插值      173 基准 · 回归
164 正则 · 词法        174 契约 · 测试
165 词法 · 语法        175 最小 · 依赖
166 语法 · 解析        176 包 · 发布
167 抽象语法 · 树      177 生态 · 库
168 格式化 · 打印      178 文档 · 测试
169 打印 · 调试        179 教程 · 练习
170 调试 · 断点        180 练习 · 反馈
```

**J. 理念与设计**
```
181 反馈 · 循环        191 线程 · 局部
182 语言 · 设计        192 求值 · 策略
183 设计 · 美学        193 急切 · 求值
184 简单 · 完备        194 按需 · 编译
185 正交 · 组合        195 需求分析
186 一致性 · 冗余      196 箭头 · 选择
187 局部 · 推断        197 循环 · 不动
188 推断 · 提示        198 递归 · 下降
189 默认 · 严格        199 权衡 · 取舍
190 可变 · 单元        200 张力 · 平衡
```

---

# 二、语言设计：**Vela**

> 取自南十字座船帆座。信条：**Pure core, explicit effects, total programs.**
> （纯核、显效、全程序）

---

## 0. 一句话定位

Vela 是一门**惰性求值、默认全函数性、代数效应（algebraic effects）、行多态记录、渐进类型、线性资源**的通用函数式语言。它把 OCaml 的工程骨架、Haskell 的代数效应思想、Koka 的效果标注、Scala 3 的模式匹配 ergonomics 缝合进一套 12 个关键字的正交语法里。

| 灵感词 | 在设计中的落点 |
|---|---|
| 惰性 · 递归 / 需求 · 严格 | 非严格求值默认，显式 `strict` 标注 |
| 代数 · 效应 / 效应 · 行 | 效应是一等公民，签名带效应行 |
| 沙漏 · 归还 / 线性 · 资源 | 线性类型 + `with` 语法，编译器强制释放 |
| 穷尽 · 检查 / 空指针 · 黑洞 | 无 null，匹配必须穷尽，全函数性检查 |
| 诊断 · 反例 / 错误消息 · 位置 | 类型错误自动生成最小反例 |
| 结构化 · 并发 / 邮箱 · 队列 | Actor + `par` 作用域，离开即 join |
| 双向 · 检查 / 局部 · 推断 | 双向类型检查，局部推断 + 全局提示 |

---

## 1. 五条信条（Principles）

1. **一切皆表达式，副作用写在签名上。** 没有"纯函数里偷偷做 IO"，没有全局变量，`! {io}` 写不出来就编译不过。
2. **一切可穷尽。** 没有 `null`、没有未定义函数、没有未初始化变量。所有 `case` 必须覆盖；编译器给**最小反例**告诉你漏了什么。
3. **数据不可变，资源必线性。** 普通值随便共享复用；`lin File`、`lin Socket` 这类资源必须在 `with` 块里用完，编译器插入关闭，漏了报错。
4. **类型是文档。** 每个类型检查错误都带源码位置、期望/实际、以及一个反例输入。
5. **惰性默认，策略可选。** 非严格求值让无限流、协程、惰性树成为自然产物；热点处可 `strict`/`force`。

---

## 2. 词法与布局

* 缩进布局（Layout 算法，类似 Python 但有 `where` 块与 `;` 分隔）
* 注释：`--` 行注释，`{- -}` 块注释（可嵌套）
* 标识符：`snake_case`，运算符由字符组成，全局可定义
* 12 个保留字：`module open type record effect actor fn let in where case of if then else match import export as`

```python
module Geometry where

type Shape =
  | Circle(Float)
  | Rect { w :: Float, h :: Float }
  | Point

record Figure { name :: String, shape :: Shape }

area : Shape -> Float
area s = case s of
  Circle r     -> π * r * r
  Rect { w, h} -> w * h
  Point         -> 0.0
```

**EBNF 骨架**

```ebnf
program    := module*
module     := 'module' CapId 'where' decl*
decl       := typeDecl | effectDecl | actorDecl | sig | def | import
typeDecl   := 'type' Id '=' ('|'? ctor)+ | 'record' Id '{' field* '}'
sig        := tcId ':' quant* '->' type ('!' '{' eff* '}')?
def        := ('fn')? opId param+ '=' expr 'where' decl*
expr       := lambda | case | if | let | do | binop | postfix | atom
lambda     := ('fn'|'\'|ident) param+ '->' expr
do         := 'run' '{' stmt* '}'
stmt       := pat '<-' expr | expr ';'
postfix    := atom ('|> ' expr)* ('as' ident)?
```

---

## 3. 类型系统

### 3.1 核心：HM + Kind 多态 + 行多态

```python
type Named r = { name :: String | r }        -- 行多态记录
get : forall r. { a :: Int | r } -> Int
get rec = rec.a

swap' : { x :: a, y :: b | r } -> { x :: b, y :: a | r }   -- 结构化换位
```

* **种类**：`Type`、`Row k`、`Effect`、`{ row: Row k }`（行上的箭头），`forall` 可提升到 kind 层。
* **子类型**：记录宽度子类型 + 深度子类型；**效应逆变**（`! {io, state} <: ! {io}`：能做的事多的人可当作做事少的人用）。

### 3.2 代数数据类型

```python
type Tree a
  = Leaf
  | Node { left :: Tree a, value :: a, right :: Tree a }

type Expr = Num(Int) | Add(Expr, Expr) | Neg(Expr) | Let(String, Expr, Expr)
```

支持 `type` 同构别名、`type abstract T`（模块私有表示，跨模块只读不造）、GADT 风格的**索引类型**（`type Vec :: Nat -> Type -> Type`）。

### 3.3 索引 GADT（轻量）

```python
type Vec :: Nat -> Type -> Type where
  Nil  :: Vec Z a
  Cons :: a -> Vec n a -> Vec (S n) a

head : Vec (S n) a -> a
head (Cons x _) = x          -- 编译器知道 n 是 S m
```

### 3.4 类型类：单分派 + 结构化

```python
class Show a where
  show :: a -> String

instance Show Int  where show n = showNat n
instance Show Bool where show b = if b then "true" else "false"

showAll : (Show a, Show b) => (a, b) -> String     -- 约束写在参数上（显式字典）
showList : [Show a] => List a -> String              -- 约束集量化
```

### 3.5 渐进类型（Gradual）

边界处用 `?T`（未知）与 `Any`（真动态）：

```python
userInput : ?Int                  -- 未解析的输入，可能是任何东西
unsafeCoerce : Any -> a           -- 需 import Unsafe，类型检查器会警告点

safe : (Coerce a Int) => a -> Int -- 可证转换自动收窄
```

### 3.6 无 null、无未定义

* 必须用 `Option a`（`None | Some a`）与 `Result a e`（`Ok a | Err e`）。
* 匹配穷尽性由**判定树 + 矩阵**检查，缺失时报反例：`case x of Some y -> ...` 缺 `None` 时输出 `missing case None`。
* **全函数性检查**：所有递归要么结构化，要么带终止度量（大小/下界），要么显式 `diverge`。

```python
size : List a -> Nat
size xs = case xs of
  []       -> 0
  _ :: rest -> 1 + size rest    -- 结构递归，OK

collatz : Nat -> Bool
collatz n = diverge "此函数不终止"
  where go m = go (if m % 2 == 0 then m / 2 else 3 * m + 1)
```

---

## 4. 效应系统（Vela 的心脏）

### 4.1 声明效应

效应就是一组**操作**（纯函数），签名上用 `! {..}` 标注：

```python
effect Console =
  emit   :: String -> Unit
  flush  :: Unit -> Unit

effect State s =
  get    :: Unit -> s
  put    :: s -> Unit

effect Choice =
  choose :: Bool -> Bool          -- 用于回溯/非确定
```

### 4.2 效应签名与推断

```python
countLines :: String -> Nat ! {Console}
countLines src = run {
  emit "hello"
  flush ()
  42
}
```

`run` 块是 do-notation：`x <- e`（bind）、`e;`（seq）、末尾为 return。效应行由检查器自动推断并**上转（效应多态）**——`countLines` 实际只有 `{Console}`，不会被多标。

### 4.3 句柄：`handle`，默认深处理

```python
count : String -> Nat ! {Console}
count src = handle (emit src) with
  return x          = 1
  emit s k          = 1 + k ()
  flush k           = k ()
```

* **深处理（deep）**：`k` 递归运行余下计算，内部同名 op 也被捕获。
* **浅处理（shallow）**：`handle shallow ...` 只捕获一层，适合调度器。

### 4.4 遮蔽与提升：把"效应"关进"效应"

```python
-- 提纯：一个带 IO 的函数，包装成纯的
pure' : (a -> b ! {io, fs}) -> (a -> b)
pure' f = handle shallow (f) with
  return x        = x
  emit s k        = s :: k ()        -- 故意不处理，落回上层
  read p k        = panic "pure 被违反"   -- 编译期若真这么用会报错
```

更实际的写法：`silent { ... }` 块静默丢弃效应；`! e` 显式提升。

### 4.5 三个杀手级示例

**(a) 状态**

```python
sumTo :: Nat -> Nat ! {State Nat}
sumTo n = run {
  acc <- get ()
  fold (0 .. n) acc \a i ->
    put (a + i)
    get ()
}
```

**(b) 回溯（Choice 效应 → 带回溯的解析器，无单子、无 CPS）**

```python
type Parser = String -> [(Expr, String)]     -- 但用代数效应写得更干净：

parseExpr :: String -> Expr ! {Choice, Fail String}
parseExpr s = handle (exprp s) with
  return e            = e
  choose b k          = if b then k true else k false
  fail msg k          = panic "不可达：Fail 只在空输入时调用"

-- exprp 内部用 choose 试探，失败自动回滚
exprp : String -> Expr ! {Choice, Fail String}
exprp ts = run {
  t <- atom ts
  more <- choose (t.rest ≠ "")
  if more then
    op <- match (t.next, t.rest) of
            ('+', u) -> Some (Add  (t.atom, `atom u))
            ('*', u) -> Some (Mul  (t.atom, `atom u))
            _        -> None
    case op of
      Some (Add a, f) -> Add a <$> exprp (f t.rest)
      Some (Mul a, f) -> Mul a <$> exprp (f t.rest)
      None            -> t.atom
  else t.atom
}
```

> 一句话卖点：**回溯、状态、异常、Nondeterminism 全是同一个 `handle` 的实例**，不是十种不同的库。

**(c) 错误：两种风格共存**

```python
-- 1. Result 显式（库边界首选）
parseNat :: String -> Result Nat String

-- 2. 效应（内部自由）
effect Fail e = fail :: e -> Never

firstJust :: [Result a e] -> Result a e
firstJust xs = handle (go xs) with
  return r = r
  fail e k = Err e
```

### 4.6 标准效应库（`Vela.Fx`）

| 效应 | 操作 | 用途 |
|---|---|---|
| `State s` | get/put | 局部可变量 |
| `Except e` | throw | 短路 |
| `Reader r` | ask/local | 配置作用域 |
| `Choice` | choose | 回溯、非确定 |
| `Trace` | mark/spy | 调试，零运行时开销（被处理后 DCE） |
| `IO` | 全部真实世界 | 受沙盒权限约束 |
| `Chan t` | send/recv/select | 结构化并发 |
| `File`(lin) | open/read/write | 线性资源，自动 close |
| `Seed` | random | 可重放的伪随机 |
| `Budget` | spend | 限额/超时，可嵌套叠加 |

---

## 5. 语法糖（正交组合的体现）

```python
xs |> filter even_ |> map (*2) |> sum          -- 管道
xs <| sum                                     -- 反管道（反过来的读法）
compose f g x                                  -- f ∘ g
xs |> map (square >>> show)                     -- 函数运算符
[ x*x | x <- 1..10, x % 3 ≠ 0 ]                 -- 列表推导
{ k: v | k <- keys, v <- lookup k table }       -- 字典推导
first [ y | y <- ys, isGood y ]                 -- 首选项，无 Option 噪声
nums <- [1,2,3]; doubled <- `map (*2) nums    -- run 块内反引号消除双单子噪声
"area = " ++ show (area shape)                  -- 字符串插值 + 拼接
(==>) point { x = 1, y = 2 }                    -- 记录更新糖
{x = 1, ..rest}                                -- 记录解构 + 剩余
[p, q, ..tail]                                 -- 列表模式
1..=10                                          -- 区间模式
Sym(n) as sym when n > 0                        -- 守卫 + 别名
(x :: xs) is nonempty                           -- 视图模式
```

**穷尽性一眼可见**：

```python
format s = case s of
  Circle r        -> "圆 "   ++ r9 r
  Rect { w = 0 } -> "退化"
  Rect { w, h }   -> "矩形 " ++ r9 w ++ "×" ++ r9 h
  Point           -> "点"
```

编译器保证这已经覆盖全部 `Shape`。

---

## 6. 线性类型与 `with`：沙漏必须归还

```python
-- 线性值只能用一次，编译器跟踪
readAll :: Path -> Bytes ! {fs, error Error}
readAll p = with open p as h do          -- h :: lin FileHandle
  h.seek Begin
  buf <- h.readAllBytes                 -- 线性能力随类型传递
  emit ("读了 " ++ show (bytesLen buf) ++ " 字节")
  buf                                   -- 离开 with 自动 close/flush
```

* 类型标注 `lin T` / `affine T`（可丢一次）/ `unrestricted T`（普通不可变值）。
* `copy` 关键字显式放弃线性性；编译器用借用检查 + 逃逸分析保证不产生悬垂句柄。
* 逃逸分析结果直接喂给运行时：线性句柄走**栈上槽位**，零堆分配、零析构函数。

---

## 7. 并发：Actor + 结构化作用域

```python
actor Counter(initial :: Int):
  count : Int = initial

  bump :: Int -> Int
  bump by = { count = count + by; count }

main = par {                        -- 结构化：离开即 join，异常即取消全体
  c <- spawn (Counter 0)
  pool <- spawn (Worker 4)
  r <- ask c (bump 5)               -- 消息 + 回复（一次性）
  tell pool (Job r)                 -- 消息 + 不回复
  timeout 3s { await pool }
  emit (show r) ! {Console}
}
```

* **无共享可变状态**：Actor 私有状态只在消息处理间隙修改 → 天然无数据竞争。
* `select { ch1 -> ..; ch2 -> .. }` 来自 `Chan` 效应，超时也是效应。
* `vela run --deterministic` 用种子化的 `Seed` + `Trace` 记录调度，**可确定性重放**，测试并发 bug 像测纯函数。

---

## 8. 编译实现路线

```
源码 → 增量解析(带错误恢复) → 双向类型检查 → 效应检查 → VIR(SSA) → 优化 → 后端
```

**VIR 关键设计**

| 阶段 | 做法 | 灵感词 |
|---|---|---|
| 模式匹配 | 编译为**判定树 + 构造器索引 switch** | 穷尽 · 检查 |
| 效应 | 一等 `handle` 降为"op 标签 + 分派表"，多处理器的 op tag 做**归一化**（尾调用、oneof 优化） | 代数 · 效应 |
| 类型类 | 单分派虚表 + **谓词特化**（热路径去虚化） | 去虚化 / 谓词 · 专门化 |
| 渐进边界 | inline cache + 形状缓存 | 缓存 · 行 |
| 尾调用 | 强制尾位置优化，无例外 | 尾调用 · 栈 |
| 资源 | 线性值用区域 + 栈槽，免 GC 压力 | 沙漏 · 归还 / 区域 · 推断 |
| GC | 不可变堆：移动式分代 + 写屏障可关；`Trace` 效应被处理后 DCE | 分代 · 假说 |

后端：原生（自研或 LLVM）、WASM、JS。编译缓存以**依赖图 + 内容哈希**为单位，增量重建通常 <50ms。

---

## 9. 工具链

```bash
vela new myapp          # 脚手架
vela check              # 全量检查，报错带反例
vela check --explain    -- 解释为什么这个推断成立/失败
vela repl               # :type, :effects, :kind, :holes 全都直接问
vela test --fuzz       -- 属性 + 模糊
vela fmt               # 唯一格式化器，零分歧
vela bench --compare   -- 基准回归，CI 拦退化
```

**报错长这样**（呼应"诊断 · 反例"）：

```
error[E0031]: non-exhaustive match
  --> src/shape.v:14:1
   |
14 | case s of
   | ^^^^^^ missing pattern for `Rect { w = 0 }`  <-- 反例
   |   最小反例: Rect { w = 0, h = 3 }
   |   加入该分支，或改用 `Rect { w, h } when w ≠ 0`
```

---

## 10. 一段完整程序（把所有特性串起来）

```python
module Report where

import Vella.Fx as Fx
import Vella.Text as T

effect Console =
  emit :: String -> Unit

-- 线性文件句柄，编译器保证关闭
countWords :: Path -> Result Nat Text ! {Console, fs, error Text}
countWords p =
  with open p as h do
    text <- h.readAllUtf8                      -- lin 能力用掉
    ws    <- Fx.trace ("tokens: " ++ T.words text)
    emit (T.lines ws |> length |> show)
    pure (ws |> length)
  where err (IoError m) = Err (T.pretty m)
```

调用者看到的一切都是**值**：`Result Nat Text ! {Console}` —— 可比较、可缓存、可快照；副作用只有一条 `emit`，其余是纯的。

---

## 11. 与邻居的差异（诚实对照）

| 维度 | Haskell | OCaml | Scala 3 | **Vela** |
|---|---|---|---|---|
| 效应 | Free/IO monad + monad transformer 栈 | 无内建 | effect 限定符（要写 context 栈） | **代数效应 + 行多态**，`handle` 自由嵌套 |
| 错误 | `Either` / `throwIO` / `ExceptT` 三套 | Result + 异常 | Either + Try + EitherT | `Result`（边界）+ `Except` 效应（内部） |
| 空值 | Maybe | option | null + Option 并存 | 只有 `Option`，无 null |
| 全函数性 | 部分函数合法 | 合法 | 合法 | **默认全函数性检查**，`diverge` 需显式 |
| 资源 | `bracket` 约定 | `Fun.protect` | `Using` | **`lin` 类型 + `with`，编译期强制** |
| 线性类型 | LinearTypes 扩展 | 无 | 无 | 内建 |
| 并发 | STM + forkIO（易泄漏） | Domains | Future | **结构化 `par` + Actor** |
| 类型 | 全静态 | 全静态 | 静态 | **渐进**（`?T` / `Any`，边界内全静态） |
| 语法 | 布局 + `do` | 分号式 | 花括号 + 缩进 | 布局 + `run` 块 + 管道，双风格 |

---

## 12. 已知风险与取舍（199 权衡 · 取舍）

1. **效应多态 + 类型类 + 种类推断三重约束**会让错误信息爆炸。
   *对策*：分阶段推断（先类型后效应再类），全部错误定位到引入行并给反例。
2. **全函数性检查**会拒绝很多"实践上终止"的程序（朴素斐波那契用不了）。
   *对策*：`[diverges]` 注解 + 可证明终止的库函数白名单；把负担放在写库的人身上。
3. **线性类型 × 垃圾回收**：既要 move 又要 GC，逃逸分析必须足够强。
   *对策*：线性值优先落栈/区域，逃逸则显式 `copy`，绝不静默。
4. **渐进类型**成本：动态形状会有 megamorphic 缓存。
   *对策*：inline cache + 反馈引导的特化，边界明确标注 `// dynamic`。

---

## 13. 路线图

* **v0.1** 纯核：布局、ADT、模式匹配、HM + 行多态记录、惰性求值、判定树编译、原生后端。
* **v0.3** 代数效应：`handle` 深浅、效应多态、标准效应库、全函数性检查。
* **v0.6** 线性类型与 `with`、Actor 与结构化并发、`--deterministic` 重放。
* **v0.8** 渐进类型、索引 GADT、宏与卫生展开、derive。
* **v1.0** 增量检查器、对抗式报错信息、LSP、性能对标 OCaml native。

---

## 14. 收尾：一段语言自述

> 我叫 Vela。
> 我的默认值是惰性的，因为大多数值你还没问它就不该算（001 惰性 · 递归）。
> 我把副作用写进签名，因为藏起来的 IO 迟早会从缝隙里漏出来（003 代数 · 效应）。
> 我没有 null，因为"缺失"是一种需要你面对的形状，不是可以糊弄过去的黑洞（019 空指针 · 黑洞）。
> 我的资源是线性的，因为我像沙漏一样，借出去就必须还回来，编译器替我记着（025 沙漏 · 归还）。
> 我的报错带反例，因为我不想让你猜，我想让你看一眼最小反例就懂（113 诊断 · 反例）。
> 我的并发是结构化的，因为我不会让线程在我的作用域之外偷偷活着（051 结构化 · 并发）。
> 我的组合是正交的：管道、推导、块、管道之间可以任意套娃，只要一个 `->`（185 正交 · 组合）。
> 我在张力之间保持平衡（200 张力 · 平衡）：既像 Haskell 一样抽象，又像 OCaml 一样能落地；既想全函数性，又不拦你写"这个函数不终止"。
