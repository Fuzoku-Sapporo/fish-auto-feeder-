import asyncio
import json
import os
from datetime import datetime, timedelta
from bleak import BleakClient, BleakScanner

CONFIG_FILE = "feeding_config.json"
MICROBIT_ADDRESS = None
UART_TX_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"

# グローバル変数
last_feed_time = None
feeding_interval = 12 * 60 * 60  # 12時間（秒単位）

def load_config():
    """設定ファイルから設定を読み込み"""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    else:
        default_config = {
            "feeding_interval_hours": 12,
            "enable_notifications": True
        }
        save_config(default_config)
        return default_config

def save_config(config):
    """設定をファイルに保存"""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

def save_last_feed_time():
    """最後の給餌時刻をファイルに保存"""
    global last_feed_time
    with open("last_feed.json", 'w') as f:
        json.dump({
            "last_feed_time": last_feed_time.isoformat() if last_feed_time else None
        }, f)

def load_last_feed_time():
    """保存された最後の給餌時刻を読み込み"""
    global last_feed_time
    if os.path.exists("last_feed.json"):
        with open("last_feed.json", 'r') as f:
            data = json.load(f)
            if data["last_feed_time"]:
                last_feed_time = datetime.fromisoformat(data["last_feed_time"])
            return
    last_feed_time = datetime.now()

def reset_feed_timer():
    """給餌タイマーをリセット"""
    global last_feed_time
    last_feed_time = datetime.now()
    save_last_feed_time()

def get_time_until_next_feed():
    """次の給餌までの時間を計算"""
    global last_feed_time
    if not last_feed_time:
        return 0
    
    next_feed_time = last_feed_time + timedelta(seconds=feeding_interval)
    time_until = (next_feed_time - datetime.now()).total_seconds()
    
    return max(0, time_until)

def format_time_remaining(seconds):
    """秒を時間:分:秒にフォーマット"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"

async def scan_microbit():
    """マイクロビットをスキャン"""
    global MICROBIT_ADDRESS
    
    print("📡 マイクロビットをスキャン中...")
    devices = await BleakScanner.discover()
    
    for device in devices:
        if "micro:bit" in device.name or device.name.startswith("BBC"):
            MICROBIT_ADDRESS = device.address
            print(f"✓ 見つかりました: {device.name}")
            return device.address
    
    return None

async def send_feed_command(client, label="", is_manual=False):
    """給餌コマンドを送信"""
    global last_feed_time
    
    try:
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"\n[{timestamp}] 🐟 {label}")
        
        # マイクロビットにコマンド送信
        await client.write_gatt_char(UART_TX_UUID, b"feed\n")
        await asyncio.sleep(0.5)
        
        # タイマーをリセット
        reset_feed_timer()
        print(f"[{timestamp}] ✓ 給餌完了")
        print(f"⏱️  タイマーリセット - 次回給餌: 12時間後\n")
        
    except Exception as e:
        print(f"✗ エラー: {e}\n")

async def schedule_task(client):
    """12時間ごとの自動給餌タスク"""
    global last_feed_time
    
    while True:
        try:
            time_until_next = get_time_until_next_feed()
            
            if time_until_next <= 0:
                # 給餌実行
                await send_feed_command(client, "【定時 自動給餌】")
            
            # 次のチェックまで待機（1分ごと）
            await asyncio.sleep(60)
        
        except Exception as e:
            print(f"✗ スケジュールエラー: {e}")
            await asyncio.sleep(60)

async def status_display_task():
    """ステータス表示タスク（5分ごと）"""
    while True:
        try:
            time_until_next = get_time_until_next_feed()
            time_str = format_time_remaining(time_until_next)
            
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp}] ⏱️  次回給餌まで: {time_str}")
            
            await asyncio.sleep(300)  # 5分ごと
        
        except Exception as e:
            print(f"✗ 表示エラー: {e}")
            await asyncio.sleep(300)

async def manual_control(client, config):
    """手動制御インターフェース"""
    loop = asyncio.get_event_loop()
    
    while True:
        try:
            command = await loop.run_in_executor(
                None,
                input,
                "\n【コマンド】feed/status/interval/exit: "
            )
            
            command = command.strip().lower()
            
            if command == "feed":
                await send_feed_command(client, "【手動】今すぐ給餌", is_manual=True)
            
            elif command == "status":
                # ステータス表示
                time_until_next = get_time_until_next_feed()
                time_str = format_time_remaining(time_until_next)
                
                if last_feed_time:
                    last_str = last_feed_time.strftime("%Y-%m-%d %H:%M:%S")
                    print(f"\n📊 給餌ステータス:")
                    print(f"   最後の給餌: {last_str}")
                    print(f"   次回給餌まで: {time_str}")
                else:
                    print("   まだ給餌記録がありません")
            
            elif command == "interval":
                # 給餌間隔を変更
                try:
                    hours = int(input("給餌間隔を時間で入力してください (例: 12): "))
                    if hours > 0:
                        global feeding_interval
                        feeding_interval = hours * 60 * 60
                        config["feeding_interval_hours"] = hours
                        save_config(config)
                        reset_feed_timer()
                        print(f"✓ 給餌間隔を {hours} 時間に変更しました")
                        print(f"  タイマーをリセットしました")
                    else:
                        print("✗ 正の数を入力してください")
                except ValueError:
                    print("✗ 有効な数値を入力してください")
            
            elif command == "exit":
                print("🛑 終了します")
                break
            
            else:
                print("❓ コマンド: feed(手動), status(確認), interval(間隔変更), exit(終了)")
        
        except EOFError:
            break
        except Exception as e:
            print(f"✗ エラー: {e}")

async def main():
    """メインプログラム"""
    
    # 設定読み込み
    config = load_config()
    
    # グローバル変数設定
    global feeding_interval, last_feed_time
    feeding_interval = config["feeding_interval_hours"] * 60 * 60
    
    # 前回の給餌時刻を読み込み
    load_last_feed_time()
    
    # マイクロビットスキャン
    if not await scan_microbit():
        print("✗ マイクロビットが見つかりません")
        return
    
    # Bluetooth接続
    async with BleakClient(MICROBIT_ADDRESS) as client:
        print("✓ 接続成功\n")
        
        # 初期ステータス表示
        time_until_next = get_time_until_next_feed()
        time_str = format_time_remaining(time_until_next)
        
        if last_feed_time:
            last_str = last_feed_time.strftime("%H:%M:%S")
            print(f"📊 初期ステータス:")
            print(f"   最後の給餌: {last_str}")
            print(f"   給餌間隔: {config['feeding_interval_hours']} 時間")
            print(f"   次回給餌まで: {time_str}\n")
        else:
            print(f"📊 初回起動 - タイマーをリセットしました\n")
        
        # タスクを並行実行
        schedule_task_handle = asyncio.create_task(schedule_task(client))
        status_task_handle = asyncio.create_task(status_display_task())
        manual_task_handle = asyncio.create_task(manual_control(client, config))
        
        try:
            await asyncio.gather(schedule_task_handle, status_task_handle, manual_task_handle)
        except KeyboardInterrupt:
            print("\n🛑 終了します")
        finally:
            schedule_task_handle.cancel()
            status_task_handle.cancel()
            manual_task_handle.cancel()
            save_last_feed_time()

if __name__ == "__main__":
    print("🐠 自動給餌システム v3.0 (12時間タイマー版)")
    print("=" * 50)
    asyncio.run(main())