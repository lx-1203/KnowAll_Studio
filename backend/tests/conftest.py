"""Shared fixtures for KnowAll_Studio backend tests."""
import pytest
from unittest.mock import MagicMock, AsyncMock


@pytest.fixture
def mock_db_session():
    """Mock async database session with basic ORM operations.

    Supports: session.get(), session.execute(), session.add(),
    session.flush(), session.commit(), session.refresh()
    """
    session = AsyncMock()

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    session.execute.return_value = mock_result
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    async def mock_get(model, pk):
        return None
    session.get = AsyncMock(side_effect=mock_get)

    return session


@pytest.fixture
def mock_api_client():
    """Mock API client that returns a fake LLM response with .content attribute."""
    client = MagicMock()
    response = MagicMock()
    response.content = "这是模拟的LLM生成内容。\n\n## 一级标题\n这是第一级知识点的解释内容。\n\n### 二级标题\n详细的知识点说明。"
    client.generate = AsyncMock(return_value=response)
    return client


@pytest.fixture
def sample_markdown():
    """A realistic 3-level Chinese Markdown text for testing extract_nodes_from_markdown."""
    return """# 计算机网络基础

计算机网络是现代信息技术的基础设施，涵盖从物理层到应用层的完整协议栈。

## OSI七层参考模型 🔴【必考】

OSI（Open Systems Interconnection）模型是国际标准化组织提出的网络通信参考标准，
将网络通信分为七个层次，每一层向上层提供服务。

### 物理层

物理层负责比特流的透明传输，定义了接口的机械、电气、功能和过程特性。
常见的物理层设备包括中继器和集线器。

关联概念：数据链路层、传输介质、信号编码

### 数据链路层

数据链路层将不可靠的物理链路变为可靠的数据链路，主要功能包括成帧、差错控制和流量控制。
常见的数据链路层协议有以太网（Ethernet）、PPP等。

示例：以太网帧格式中，前导码用于时钟同步，目的地址和源地址各占6字节。

### 网络层

网络层负责将数据从源端传输到目的端，核心功能是路由选择和逻辑寻址。
IP协议是网络层最重要的协议。

举例：IP地址分为网络位和主机位，子网掩码用于区分二者。

## TCP/IP协议栈 🟡【重点】

TCP/IP协议栈是互联网事实上的标准，包含应用层、传输层、网络层和网络接口层四个层次。

关联内容：OSI模型对比、协议封装过程

### TCP可靠传输机制

TCP通过序列号、确认应答、重传超时和窗口控制实现可靠的数据传输。
三报文握手建立连接，四报文挥手释放连接。

示例：TCP三次握手过程中，客户端发送SYN报文，服务器回复SYN+ACK，客户端再发送ACK确认。

### UDP无连接传输

UDP是无连接的传输协议，不保证可靠交付，但具有低延迟的优势，
适用于实时音视频传输和DNS查询等场景。

## 网络安全基础 🟢【了解】

网络安全是保障数据机密性、完整性和可用性的重要技术领域。

关联概念：加密算法、身份认证、访问控制

### 对称加密与非对称加密

对称加密使用同一密钥进行加密和解密，效率高但密钥分发困难；
非对称加密使用公私钥对，安全性高但计算开销大。

举例：AES是典型的对称加密算法，RSA是广泛应用的非对称加密算法。
"""


@pytest.fixture
def sample_nodes():
    """A list of dicts representing KnowledgePointNode data with L1/L2/L3 hierarchy."""
    return [
        {
            "id": "kp_doc01_L1_01",
            "parent_id": None,
            "level": 1,
            "sequence": 1,
            "title": "计算机网络基础",
            "tag": "重点",
            "related_concepts": "",
            "examples": "",
            "explanation": "计算机网络是现代信息技术的基础设施。",
        },
        {
            "id": "kp_doc01_L2_01_01",
            "parent_id": "kp_doc01_L1_01",
            "level": 2,
            "sequence": 1,
            "title": "OSI七层参考模型",
            "tag": "必考",
            "related_concepts": "数据链路层、传输介质、信号编码",
            "examples": "",
            "explanation": "OSI模型是国际标准化组织提出的网络通信参考标准。",
        },
        {
            "id": "kp_doc01_L3_01_01_01",
            "parent_id": "kp_doc01_L2_01_01",
            "level": 3,
            "sequence": 1,
            "title": "物理层",
            "tag": "重点",
            "related_concepts": "数据链路层、传输介质、信号编码",
            "examples": "",
            "explanation": "物理层负责比特流的透明传输。",
        },
        {
            "id": "kp_doc01_L3_01_01_02",
            "parent_id": "kp_doc01_L2_01_01",
            "level": 3,
            "sequence": 2,
            "title": "数据链路层",
            "tag": "重点",
            "related_concepts": "",
            "examples": "以太网帧格式中，前导码用于时钟同步。",
            "explanation": "数据链路层将不可靠的物理链路变为可靠的数据链路。",
        },
        {
            "id": "kp_doc01_L3_01_01_03",
            "parent_id": "kp_doc01_L2_01_01",
            "level": 3,
            "sequence": 3,
            "title": "网络层",
            "tag": "重点",
            "related_concepts": "",
            "examples": "IP地址分为网络位和主机位。",
            "explanation": "网络层负责将数据从源端传输到目的端。",
        },
        {
            "id": "kp_doc01_L2_01_02",
            "parent_id": "kp_doc01_L1_01",
            "level": 2,
            "sequence": 2,
            "title": "TCP/IP协议栈",
            "tag": "重点",
            "related_concepts": "OSI模型对比、协议封装过程",
            "examples": "",
            "explanation": "TCP/IP协议栈是互联网事实上的标准。",
        },
        {
            "id": "kp_doc01_L3_01_02_01",
            "parent_id": "kp_doc01_L2_01_02",
            "level": 3,
            "sequence": 1,
            "title": "TCP可靠传输机制",
            "tag": "必考",
            "related_concepts": "",
            "examples": "TCP三次握手：SYN -> SYN+ACK -> ACK",
            "explanation": "TCP通过序列号、确认应答实现可靠传输。",
        },
        {
            "id": "kp_doc01_L3_01_02_02",
            "parent_id": "kp_doc01_L2_01_02",
            "level": 3,
            "sequence": 2,
            "title": "UDP无连接传输",
            "tag": "了解",
            "related_concepts": "",
            "examples": "",
            "explanation": "UDP是无连接的传输协议，不保证可靠交付。",
        },
        {
            "id": "kp_doc01_L2_01_03",
            "parent_id": "kp_doc01_L1_01",
            "level": 2,
            "sequence": 3,
            "title": "网络安全基础",
            "tag": "了解",
            "related_concepts": "加密算法、身份认证、访问控制",
            "examples": "",
            "explanation": "网络安全是保障数据机密性的重要技术领域。",
        },
        {
            "id": "kp_doc01_L3_01_03_01",
            "parent_id": "kp_doc01_L2_01_03",
            "level": 3,
            "sequence": 1,
            "title": "对称加密与非对称加密",
            "tag": "重点",
            "related_concepts": "",
            "examples": "AES是典型的对称加密算法，RSA是广泛应用的非对称加密算法。",
            "explanation": "对称加密使用同一密钥进行加密和解密。",
        },
    ]
