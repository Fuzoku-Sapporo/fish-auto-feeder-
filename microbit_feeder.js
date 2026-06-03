// 変数をコードの一番上で宣言
let lastFeedTime = 0
let timeUntilNext = 0
const FEEDING_INTERVAL = 43200000 // 12時間（ミリ秒）

bluetooh.startUartService()

bluetooh.onUartDataReceived(serial.delimiters(Delimiters.NewLine), function () {
    if (serial.readString() == "feed") {
        pins.servoWritePin(AnalogPin.P16, 180)
        basic.pause(1000)
        pins.servoWritePin(AnalogPin.P16, 0)
        lastFeedTime = input.runningTime()
    }
})

input.onButtonPressed(Button.A, function () {
    // ボタンA: 手動給餌
    pins.servoWritePin(AnalogPin.P16, 180)
    basic.pause(1000)
    pins.servoWritePin(AnalogPin.P16, 0)
    lastFeedTime = input.runningTime()
    basic.showIcon(IconNames.Happy)
    basic.pause(500)
})

input.onButtonPressed(Button.B, function () {
    // ボタンB: 次回給餌時刻を表示
    timeUntilNext = FEEDING_INTERVAL - (input.runningTime() - lastFeedTime)
    basic.showNumber(Math.round(timeUntilNext / 3600000))
})

basic.forever(function () {
    // 12時間ごとに自動給餌
    if (input.runningTime() - lastFeedTime >= FEEDING_INTERVAL) {
        pins.servoWritePin(AnalogPin.P16, 180)
        basic.pause(1000)
        pins.servoWritePin(AnalogPin.P16, 0)
        lastFeedTime = input.runningTime()
        basic.showIcon(IconNames.Heart)
    }
    basic.pause(60000) // 1分ごとにチェック
})