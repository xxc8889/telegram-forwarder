# 🚀 Telegram Channel Forwarder

一个功能完整的Telegram频道消息搬运工具，采用**搬运组**概念，支持精细化管理不同类型的频道内容。现已升级为**Web管理界面**，提供更直观的操作体验。

## ✨ 核心特性

### 🎯 搬运组概念
- **搬运组** = 独立的转发单元，每个组有自己的源频道、目标频道和过滤规则
- **灵活配置** = 不同类型内容可以有不同的处理方式
- **精细管理** = 每个组独立的过滤规则、统计和监控

### 🌐 Web管理界面
- **现代化界面** - 响应式设计，支持暗色主题
- **安全登录** - 基于Bot验证的6位数字登录码
- **实时监控** - WebSocket实时状态更新
- **完整功能** - 所有管理功能通过Web界面操作

### 🔧 主要功能
- **定时调度** - 按时间段控制搬运组的启停
- **账号轮换** - 监听账号轮换使用，检测异常状态并自动切换
- **API池管理** - 支持多个API ID，自动分配给账号
- **智能过滤** - 过滤后没有内容自动跳过
- **配置热更新** - 无需重启修改过滤规则、发送频率、动态添加删除频道
- **并行处理** - 不同搬运组独立并行处理
- **历史搬运** - 支持搬运全部历史消息

### 🎮 基础功能
- **多账号监听** - 支持多个Telegram账号同时监听源频道
- **多Bot发送** - 轮换使用多个Bot发送消息，避免频率限制
- **媒体组检测** - 完整转发包含多张图片/视频的消息组
- **全局去重** - 避免重复转发相同消息，重启后仍有效
- **7×24小时运行** - systemd服务自动重启，稳定可靠

## 🚀 一键安装

### VPS部署

```bash
# 克隆项目
git clone https://github.com/cz881/telegram-forwarder.git
cd telegram-forwarder

# 设置权限
chmod +x scripts/*.sh

# 一键安装
./scripts/install.sh

# 运行设置向导
./scripts/setup_wizard.sh
```

### 手动配置

如果不使用设置向导，可以手动配置：

```bash
# 复制配置文件
cp .env.example .env

# 编辑配置
vim .env
```

必须配置的环境变量：
```bash
BOT_TOKEN=your_bot_token_here                    # Bot Token
ADMIN_USERS=123456789,987654321                  # 管理员用户ID
ENCRYPTION_KEY=your_32_byte_encryption_key_here  # 加密密钥
WEB_SECRET_KEY=your_web_secret_key_here          # Web密钥
```

## 🎯 使用场景示例

### 场景1：新闻搬运组 (工作时间)
```yaml
组名: 新闻搬运组
源频道: 新华社、人民日报、央视新闻
目标频道: 我的新闻频道
定时调度: 09:00-18:00 (仅工作时间运行)
过滤设置: 开启广告过滤，保留链接，删除@提及
小尾巴: 📰 新闻搬运 | 仅供参考
```

### 场景2：娱乐搬运组 (夜间运行)
```yaml
组名: 娱乐搬运组
源频道: 娱乐八卦频道、明星动态
目标频道: 我的娱乐频道
定时调度: 22:00-08:00 (夜间运行，跨天)
过滤设置: 删除链接，保留表情，开启广告过滤
小尾巴: 🎬 娱乐资讯
```

## 📱 使用流程

### 1. 启动服务
```bash
# 安装系统服务
sudo ./scripts/service.sh install

# 启动服务
./scripts/service.sh start

# 查看状态
./scripts/service.sh status
```

### 2. 访问管理界面

1. **开启Bot对话**
   - 找到你的Bot并发送 `/start`
   - 点击"🌐 打开管理后台"按钮

2. **Web登录验证**
   - 在Web页面点击"获取登录码"
   - 将6位数字登录码发送给Bot
   - 验证成功后自动跳转到管理界面

3. **配置系统**
   - 📋 **搬运组管理**：创建搬运组，配置源频道和目标频道
   - 👥 **账号管理**：添加监听账号，配置API池
   - ⚙️ **系统设置**：配置过滤器、调度、安全设置
   - 📊 **监控日志**：查看系统状态和运行日志

## 🌐 Web管理功能

### 📊 仪表板
- 系统状态总览
- 实时统计图表
- 组件运行状态
- 最近活动记录

### 📋 搬运组管理
- 创建和编辑搬运组
- 配置源频道和目标频道
- 设置过滤规则和调度时间
- 查看搬运统计和成功率

### 👥 账号管理
- 查看监听账号状态
- API池管理和分配
- 账号健康度监控
- 错误处理和重连

### ⚙️ 系统设置
- 全局过滤器配置
- 发送频率和轮换策略
- 安全设置和密钥管理
- 自动备份和清理

### 📝 日志管理
- 实时日志查看
- 日志级别过滤
- 搜索和下载功能
- 系统性能监控

## 🔧 管理工具

### 服务管理
```bash
./scripts/service.sh start          # 启动服务
./scripts/service.sh stop           # 停止服务
./scripts/service.sh restart        # 重启服务
./scripts/service.sh status         # 查看状态
./scripts/service.sh logs           # 查看日志
```

### 监控和备份
```bash
./scripts/monitor.sh                # 系统监控
./scripts/backup.sh                 # 手动备份
```

## 📊 系统要求

### 最低配置
- **系统**: Ubuntu 20.04+ / CentOS 7+ / Debian 10+
- **内存**: 1GB RAM
- **存储**: 10GB 可用空间
- **Python**: 3.8+
- **网络**: 稳定的互联网连接

### 推荐配置
- **系统**: Ubuntu 22.04 LTS
- **内存**: 2GB RAM
- **存储**: 20GB SSD
- **网络**: 境外VPS（推荐）

### 端口要求
- **8080**: Web管理界面端口（可在.env中修改）
- 确保防火墙已开放相应端口

## 🛡️ 安全建议

1. **保护敏感信息**
   - `.env` 文件包含敏感信息，务必设置正确权限
   - 加密密钥用于保护账号会话，请妥善保管

2. **定期备份**
   - 系统支持自动备份数据库和配置
   - 建议定期下载备份文件到本地

3. **监控日志**
   - 通过Web界面定期检查错误日志
   - 关注账号状态和异常告警

4. **API分配**
   - 建议1-3个账号共享一个API ID
   - 避免单个API负载过重

5. **网络安全**
   - 建议使用HTTPS（可配置反向代理）
   - 定期更新Web密钥和登录码有效期

## 🔧 故障排除

### 常见问题

1. **Web界面无法访问**
   ```bash
   # 检查服务状态
   ./scripts/service.sh status
   
   # 检查端口占用
   netstat -tlnp | grep 8080
   
   # 查看详细日志
   ./scripts/service.sh logs
   ```

2. **Bot登录验证失败**
   - 检查Bot Token是否正确
   - 确认用户ID在管理员列表中
   - 检查登录码是否在5分钟有效期内

3. **账号登录失败**
   - 检查手机号格式和API有效性
   - 确认网络连接稳定
   - 查看账号管理页面的错误信息

4. **消息不转发**
   - 检查搬运组状态和调度时间
   - 验证源频道和目标频道配置
   - 查看过滤规则设置

### 调试工具
```bash
# 查看详细日志
./scripts/service.sh logs 200

# 系统健康检查
./scripts/monitor.sh quick

# 重启所有服务
./scripts/service.sh restart
```

## 🆕 更新日志

### v1.0.0 (Web管理版)
- ✨ 全新Web管理界面
- 🔐 安全的Bot验证登录
- 📊 实时数据监控
- 🎨 现代化UI设计
- 📱 响应式移动端支持

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## ⚠️ 免责声明

本工具仅供学习和个人使用，请遵守当地法律法规和Telegram服务条款。使用者需对自己的行为负责。

## 📞 技术支持

如有问题请：
1. 查看Web界面日志: 访问管理界面 → 系统日志
2. 检查服务状态: `./scripts/service.sh status`
3. 系统健康检查: `./scripts/monitor.sh`
4. 提交 Issue 或联系维护者

---

**⭐ 如果这个项目对你有帮助，请给一个Star！**

**🌐 现在就体验Web管理界面的强大功能吧！**