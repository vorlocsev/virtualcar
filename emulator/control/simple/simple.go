// Package simple powers the beginner-friendly P2 virtual car workflow.
// The program remains a read-only J2534 emulator; these checks never modify ECU data.
package simple

import (
	"fmt"
	"sectorv-virtualcar-control/p2audit"
)

// ProfileReady verifies the 13-frame B9FB fixture for the intended model year.
// It does NOT authenticate the other fields against the OEM vehicle database.
func ProfileReady(ini []byte, expectedYear int) error {
	p := p2audit.ReadProfile(string(ini))
	for _, issue := range p.Issues {
		return fmt.Errorf("ошибка VIN/года: %s", issue)
	}
	if p.ModelYear != expectedYear {
		return fmt.Errorf("ожидался модельный год %d, найден %d", expectedYear, p.ModelYear)
	}
	if !p.StrictRouting {
		return fmt.Errorf("строгая маршрутизация CAN-HS/CAN-LS выключена")
	}
	for _, f := range p.Fixtures {
		if f.Name == "D2_50" {
			if !f.Valid {
				if len(f.Issues) != 0 {
					return fmt.Errorf("B9FB: %s", f.Issues[0])
				}
				return fmt.Errorf("ответ B9FB не прошёл проверку")
			}
			if f.Count != 13 {
				return fmt.Errorf("B9FB: нужно 13 кадров, найдено %d", f.Count)
			}
			return nil
		}
	}
	return fmt.Errorf("в профиле нет ответа CEM 0x50 B9FB")
}

// ProfileLabel is safe to display: it does not reveal full VINs.
func ProfileLabel(ini []byte) string {
	p := p2audit.ReadProfile(string(ini))
	for _, f := range p.Fixtures {
		if f.Name == "D2_50" && f.Valid && f.Count == 13 {
			switch p.ModelYear {
			case 2009:
				return "XC90 V8 2009 · VIN подготовлен (13 кадров)"
			case 2005:
				return "XC90 V8 2005 · донор (13 кадров)"
			default:
				return fmt.Sprintf("P2 %d · 13 кадров B9FB", p.ModelYear)
			}
		}
	}
	return "Нет активного ответа B9FB · нажмите «Подготовить»"
}

// Result produces a concise diagnosis of the LAST marked SectorV attempt.
// A complete D2 delivery is never presented as proof of OEM VIN acceptance.
func Result(log []byte) string {
	s := p2audit.SummarizeLog(string(log))
	if s.Entries == 0 || s.Requests50 == 0 {
		return "SectorV пока не запрашивал VIN у CEM 0x50 в последней сессии.\n\n" +
			"Нажмите «Начать тест», откройте SectorV и запустите определение автомобиля."
	}
	complete := 0
	for _, replay := range s.Replays50 {
		if replay.Complete && replay.SequenceOK {
			complete++
		}
	}
	result := fmt.Sprintf("Запросов VIN к CEM 0x50: %d\nОтветов подготовлено: %d\nКадров передано SectorV: %d\nПолных последовательностей D2: %d\n", s.Requests50, s.Staged50, s.Delivered50, complete)
	switch {
	case s.Missing50 > 0 && s.Staged50 == 0:
		result += "\nОтвет не настроен. Нажмите «Подготовить» и перезапустите SectorV."
	case complete == 0 && s.Staged50 > 0:
		result += "\nОтвет готовился, но полная доставка кадров не подтверждена. Откройте «Полный аудит»."
	case complete > 0:
		result += "\nD2 передан корректно. Принятие VIN самой программой SectorV пока не подтверждено."
	default:
		result += "\nОтвет не получен. Проверьте профиль и зарегистрированную DLL."
	}
	if s.ClosedAfter50 {
		result += "\nSectorV закрыл соединение; причина закрытия неизвестна."
	}
	return result
}
