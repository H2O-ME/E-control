document.addEventListener('DOMContentLoaded', function() {
    // E-control 命令数据
    const commands = [
        // 基础命令格式
        {
            title: '执行命令 (指定设备)',
            command: 'to+设备名+cmd+命令',
            description: '在指定设备上执行命令'
        },
        {
            title: '访问网站 (指定设备)',
            command: 'to+设备名+website+example.com',
            description: '让指定设备访问网站 (不需要https://)'
        },
        {
            title: '关闭程序 (指定设备)',
            command: 'to+设备名+poweroff',
            description: '关闭指定设备上的E-control程序'
        },
        {
            title: '列出桌面文件 (指定设备)',
            command: 'to+设备名+file+list',
            description: '列出指定设备桌面的文件'
        },
        {
            title: '获取桌面文件 (指定设备)',
            command: 'to+设备名+file+文件名.扩展名',
            description: '获取指定设备桌面上的文件'
        },
        {
            title: '列出文件夹内容 (指定设备)',
            command: 'to+设备名+file+文件夹名',
            description: '列出指定设备上桌面文件夹的内容'
        },
        {
            title: '获取文件夹中的文件 (指定设备)',
            command: 'to+设备名+file+文件夹名+文件名.扩展名',
            description: '获取指定设备上文件夹中的文件'
        },
        {
            title: '快捷指令 - 弹窗错误 (指定设备)',
            command: 'to+设备名+a',
            description: '在指定设备上显示运行库错误弹窗'
        },
        {
            title: '快捷指令 - 播放音乐 (指定设备)',
            command: 'to+设备名+b',
            description: '在指定设备上播放《Never Gonna Give You Up》'
        },
        {
            title: '获取屏幕截图 (指定设备)',
            command: 'to+设备名+screen',
            description: '获取指定设备的屏幕截图'
        },
        // 广播命令格式
        {
            title: '执行命令 (广播)',
            command: 'cmd+命令',
            description: '在所有设备上执行命令',
            isBroadcast: true
        },
        {
            title: '访问网站 (广播)',
            command: 'website+example.com',
            description: '让所有设备访问网站 (不需要https://)',
            isBroadcast: true
        },
        {
            title: '关闭程序 (广播)',
            command: 'poweroff',
            description: '关闭所有设备上的E-control程序',
            isBroadcast: true
        },
        {
            title: '列出桌面文件 (广播)',
            command: 'file+list',
            description: '列出所有设备桌面的文件',
            isBroadcast: true
        },
        {
            title: '获取桌面文件 (广播)',
            command: 'file+文件名.扩展名',
            description: '获取所有设备桌面上的文件',
            isBroadcast: true
        },
        {
            title: '列出文件夹内容 (广播)',
            command: 'file+文件夹名',
            description: '列出所有设备上桌面文件夹的内容',
            isBroadcast: true
        },
        {
            title: '获取文件夹中的文件 (广播)',
            command: 'file+文件夹名+文件名.扩展名',
            description: '获取所有设备上文件夹中的文件',
            isBroadcast: true
        },
        {
            title: '快捷指令 - 弹窗错误 (广播)',
            command: 'a',
            description: '在所有设备上显示运行库错误弹窗',
            isBroadcast: true
        },
        {
            title: '快捷指令 - 播放音乐 (广播)',
            command: 'b',
            description: '在所有设备上播放《Never Gonna Give You Up》',
            isBroadcast: true
        },
        {
            title: '获取屏幕截图 (广播)',
            command: 'screen',
            description: '获取所有设备的屏幕截图',
            isBroadcast: true
        }
    ];

    const commandsContainer = document.getElementById('commandsContainer');
    const searchInput = document.getElementById('searchInput');
    const notification = document.getElementById('notification');

    // 显示命令卡片
    function displayCommands(commandsToShow) {
        commandsContainer.innerHTML = '';
        
        // 创建标签筛选器
        const filterContainer = document.createElement('div');
        filterContainer.className = 'filter-container';
        filterContainer.innerHTML = `
            <button class="filter-btn active" data-filter="all">全部命令</button>
            <button class="filter-btn" data-filter="target">指定设备</button>
            <button class="filter-btn" data-filter="broadcast">广播命令</button>
        `;
        commandsContainer.appendChild(filterContainer);

        // 添加筛选按钮事件
        const filterButtons = filterContainer.querySelectorAll('.filter-btn');
        filterButtons.forEach(btn => {
            btn.addEventListener('click', () => {
                // 更新活动按钮样式
                filterButtons.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                
                // 筛选命令
                const filter = btn.dataset.filter;
                const filtered = commandsToShow.filter(cmd => {
                    if (filter === 'all') return true;
                    if (filter === 'target') return !cmd.isBroadcast;
                    if (filter === 'broadcast') return cmd.isBroadcast;
                    return true;
                });
                
                // 显示筛选后的命令
                renderCommands(filtered);
            });
        });

        // 初始渲染所有命令
        renderCommands(commandsToShow);
        
        // 渲染命令卡片的辅助函数
        function renderCommands(commands) {
            // 清空现有命令（保留筛选器）
            const existingFilter = commandsContainer.querySelector('.filter-container');
            commandsContainer.innerHTML = '';
            if (existingFilter) commandsContainer.appendChild(existingFilter);
            
            // 如果没有匹配的命令，显示提示
            if (commands.length === 0) {
                const noResults = document.createElement('div');
                noResults.className = 'no-results';
                noResults.textContent = '没有找到匹配的命令';
                commandsContainer.appendChild(noResults);
                return;
            }
            
            commands.forEach(cmd => {
                const card = document.createElement('div');
                card.className = `command-card ${cmd.isBroadcast ? 'broadcast' : 'target'}`;
                
                // 添加广播标签
                const tag = cmd.isBroadcast 
                    ? '<div class="command-tag broadcast-tag">广播</div>'
                    : '<div class="command-tag target-tag">指定设备</div>';
                
                card.innerHTML = `
                    ${tag}
                    <div class="command-title">${cmd.title}</div>
                    <div class="command-desc">${cmd.description}</div>
                    <div class="command-code">${cmd.command}</div>
                `;
                
                // 添加点击事件
                card.addEventListener('click', () => {
                    copyToClipboard(cmd.command);
                    showNotification(`已复制: ${cmd.command}`);
                });
                
                commandsContainer.appendChild(card);
            });
        }
    }

    // 复制到剪贴板
    function copyToClipboard(text) {
        const textarea = document.createElement('textarea');
        textarea.value = text;
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
    }

    // 显示通知
    function showNotification(message) {
        notification.textContent = message;
        notification.classList.add('show');
        
        setTimeout(() => {
            notification.classList.remove('show');
        }, 2000);
    }

    // 搜索功能
    searchInput.addEventListener('input', (e) => {
        const searchTerm = e.target.value.toLowerCase();
        const filteredCommands = commands.filter(cmd => 
            cmd.title.toLowerCase().includes(searchTerm) || 
            cmd.command.toLowerCase().includes(searchTerm) ||
            cmd.description.toLowerCase().includes(searchTerm)
        );
        displayCommands(filteredCommands);
    });

    // 初始显示所有命令
    displayCommands(commands);
});
