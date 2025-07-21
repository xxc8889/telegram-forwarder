/**
 * Telegram Forwarder 图表组件JavaScript文件
 */

// 图表配置
const ChartConfig = {
    defaultOptions: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                labels: {
                    color: '#cbd5e1',
                    font: {
                        size: 12
                    }
                }
            }
        },
        scales: {
            x: {
                grid: {
                    color: 'rgba(255, 255, 255, 0.1)'
                },
                ticks: {
                    color: '#94a3b8',
                    font: {
                        size: 11
                    }
                }
            },
            y: {
                grid: {
                    color: 'rgba(255, 255, 255, 0.1)'
                },
                ticks: {
                    color: '#94a3b8',
                    font: {
                        size: 11
                    }
                }
            }
        }
    },
    
    colors: {
        primary: '#3b82f6',
        success: '#10b981',
        warning: '#f59e0b',
        error: '#ef4444',
        info: '#06b6d4',
        gray: '#6b7280'
    }
};

// 图表实例管理
const ChartManager = {
    charts: new Map(),
    
    /**
     * 创建或更新图表
     */
    createOrUpdate(canvasId, config) {
        const existingChart = this.charts.get(canvasId);
        
        if (existingChart) {
            existingChart.destroy();
        }
        
        const canvas = document.getElementById(canvasId);
        if (!canvas) {
            console.error(`❌ 未找到画布元素: ${canvasId}`);
            return null;
        }
        
        const chart = new Chart(canvas, config);
        this.charts.set(canvasId, chart);
        
        return chart;
    },
    
    /**
     * 更新图表数据
     */
    updateData(canvasId, newData) {
        const chart = this.charts.get(canvasId);
        if (chart) {
            chart.data = newData;
            chart.update('active');
        }
    },
    
    /**
     * 销毁图表
     */
    destroy(canvasId) {
        const chart = this.charts.get(canvasId);
        if (chart) {
            chart.destroy();
            this.charts.delete(canvasId);
        }
    },
    
    /**
     * 销毁所有图表
     */
    destroyAll() {
        this.charts.forEach((chart, canvasId) => {
            chart.destroy();
        });
        this.charts.clear();
    }
};

/**
 * 创建消息统计图表
 */
function createMessageChart(canvasId, data = null) {
    const defaultData = {
        labels: Array.from({length: 24}, (_, i) => `${i}:00`),
        datasets: [{
            label: '消息数量',
            data: Array.from({length: 24}, () => Math.floor(Math.random() * 30)),
            borderColor: ChartConfig.colors.primary,
            backgroundColor: ChartConfig.colors.primary + '20',
            tension: 0.4,
            fill: true,
            pointRadius: 3,
            pointHoverRadius: 5
        }]
    };
    
    const config = {
        type: 'line',
        data: data || defaultData,
        options: {
            ...ChartConfig.defaultOptions,
            plugins: {
                ...ChartConfig.defaultOptions.plugins,
                legend: {
                    display: false
                },
                tooltip: {
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    titleColor: '#ffffff',
                    bodyColor: '#ffffff',
                    borderColor: ChartConfig.colors.primary,
                    borderWidth: 1
                }
            },
            scales: {
                ...ChartConfig.defaultOptions.scales,
                y: {
                    ...ChartConfig.defaultOptions.scales.y,
                    beginAtZero: true
                }
            }
        }
    };
    
    return ChartManager.createOrUpdate(canvasId, config);
}

/**
 * 创建成功率饼图
 */
function createSuccessRateChart(canvasId, successRate = 98.5) {
    const failureRate = 100 - successRate;
    
    const data = {
        labels: ['成功', '失败'],
        datasets: [{
            data: [successRate, failureRate],
            backgroundColor: [
                ChartConfig.colors.success,
                ChartConfig.colors.error
            ],
            borderWidth: 0,
            hoverOffset: 4
        }]
    };
    
    const config = {
        type: 'doughnut',
        data: data,
        options: {
            ...ChartConfig.defaultOptions,
            cutout: '70%',
            plugins: {
                ...ChartConfig.defaultOptions.plugins,
                legend: {
                    position: 'bottom',
                    labels: {
                        color: '#cbd5e1',
                        padding: 20,
                        usePointStyle: true
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    titleColor: '#ffffff',
                    bodyColor: '#ffffff',
                    callbacks: {
                        label: function(context) {
                            return context.label + ': ' + context.parsed + '%';
                        }
                    }
                }
            }
        }
    };
    
    return ChartManager.createOrUpdate(canvasId, config);
}

/**
 * 创建系统资源使用图表
 */
function createResourceChart(canvasId, resourceData = null) {
    const defaultData = {
        labels: ['CPU', '内存', '磁盘', '网络'],
        datasets: [{
            label: '使用率 (%)',
            data: resourceData || [25, 65, 45, 30],
            backgroundColor: [
                ChartConfig.colors.primary,
                ChartConfig.colors.success,
                ChartConfig.colors.warning,
                ChartConfig.colors.info
            ],
            borderWidth: 0
        }]
    };
    
    const config = {
        type: 'bar',
        data: defaultData,
        options: {
            ...ChartConfig.defaultOptions,
            plugins: {
                ...ChartConfig.defaultOptions.plugins,
                legend: {
                    display: false
                }
            },
            scales: {
                ...ChartConfig.defaultOptions.scales,
                y: {
                    ...ChartConfig.defaultOptions.scales.y,
                    beginAtZero: true,
                    max: 100
                }
            }
        }
    };
    
    return ChartManager.createOrUpdate(canvasId, config);
}

/**
 * 创建趋势图表
 */
function createTrendChart(canvasId, datasets = null) {
    const defaultDatasets = [
        {
            label: '今日',
            data: Array.from({length: 24}, () => Math.floor(Math.random() * 50)),
            borderColor: ChartConfig.colors.primary,
            backgroundColor: ChartConfig.colors.primary + '20',
            tension: 0.4
        },
        {
            label: '昨日',
            data: Array.from({length: 24}, () => Math.floor(Math.random() * 40)),
            borderColor: ChartConfig.colors.gray,
            backgroundColor: ChartConfig.colors.gray + '20',
            tension: 0.4
        }
    ];
    
    const data = {
        labels: Array.from({length: 24}, (_, i) => `${i}:00`),
        datasets: datasets || defaultDatasets
    };
    
    const config = {
        type: 'line',
        data: data,
        options: {
            ...ChartConfig.defaultOptions,
            interaction: {
                mode: 'index',
                intersect: false
            },
            plugins: {
                ...ChartConfig.defaultOptions.plugins,
                tooltip: {
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    titleColor: '#ffffff',
                    bodyColor: '#ffffff',
                    borderColor: ChartConfig.colors.primary,
                    borderWidth: 1
                }
            },
            scales: {
                ...ChartConfig.defaultOptions.scales,
                y: {
                    ...ChartConfig.defaultOptions.scales.y,
                    beginAtZero: true
                }
            }
        }
    };
    
    return ChartManager.createOrUpdate(canvasId, config);
}

/**
 * 创建实时监控图表
 */
function createRealtimeChart(canvasId, maxPoints = 60) {
    const initialData = Array.from({length: maxPoints}, () => 0);
    
    const data = {
        labels: Array.from({length: maxPoints}, (_, i) => i),
        datasets: [{
            label: '实时数据',
            data: initialData,
            borderColor: ChartConfig.colors.success,
            backgroundColor: ChartConfig.colors.success + '20',
            borderWidth: 2,
            fill: true,
            tension: 0.4,
            pointRadius: 0
        }]
    };
    
    const config = {
        type: 'line',
        data: data,
        options: {
            ...ChartConfig.defaultOptions,
            scales: {
                ...ChartConfig.defaultOptions.scales,
                x: {
                    ...ChartConfig.defaultOptions.scales.x,
                    display: false
                },
                y: {
                    ...ChartConfig.defaultOptions.scales.y,
                    beginAtZero: true
                }
            },
            plugins: {
                ...ChartConfig.defaultOptions.plugins,
                legend: {
                    display: false
                }
            },
            animation: {
                duration: 0
            }
        }
    };
    
    const chart = ChartManager.createOrUpdate(canvasId, config);
    
    // 添加数据更新方法
    chart.addData = function(value) {
        this.data.datasets[0].data.push(value);
        this.data.datasets[0].data.shift();
        this.update('none');
    };
    
    return chart;
}

/**
 * 创建热力图
 */
function createHeatmapChart(canvasId, heatmapData = null) {
    // 生成默认数据（7天 x 24小时）
    const defaultData = [];
    const days = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];
    
    for (let day = 0; day < 7; day++) {
        for (let hour = 0; hour < 24; hour++) {
            defaultData.push({
                x: hour,
                y: day,
                v: Math.floor(Math.random() * 100)
            });
        }
    }
    
    const data = {
        datasets: [{
            label: '活动强度',
            data: heatmapData || defaultData,
            backgroundColor: function(context) {
                const value = context.parsed.v;
                const alpha = value / 100;
                return `rgba(59, 130, 246, ${alpha})`;
            },
            borderColor: 'rgba(255, 255, 255, 0.1)',
            borderWidth: 1,
            width: ({chart}) => (chart.chartArea || {}).width / 24,
            height: ({chart}) => (chart.chartArea || {}).height / 7
        }]
    };
    
    const config = {
        type: 'scatter',
        data: data,
        options: {
            ...ChartConfig.defaultOptions,
            scales: {
                x: {
                    type: 'linear',
                    position: 'bottom',
                    min: 0,
                    max: 23,
                    ticks: {
                        stepSize: 1,
                        color: '#94a3b8',
                        callback: function(value) {
                            return value + ':00';
                        }
                    },
                    grid: {
                        color: 'rgba(255, 255, 255, 0.1)'
                    }
                },
                y: {
                    type: 'linear',
                    min: 0,
                    max: 6,
                    ticks: {
                        stepSize: 1,
                        color: '#94a3b8',
                        callback: function(value) {
                            return days[value];
                        }
                    },
