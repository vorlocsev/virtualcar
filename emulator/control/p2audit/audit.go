// Package p2audit checks local laboratory fixtures and summarizes read-only
// J2534 traffic. It never generates vehicle identities or access credentials.
package p2audit

import (
	"bufio"
	"encoding/hex"
	"fmt"
	"regexp"
	"strconv"
	"strings"
)

var vinToken = regexp.MustCompile(`\b[A-HJ-NPR-Z0-9]{17}\b`)

type Fixture struct {
	Advisories []string
	Name       string
	Target     byte
	Opcode     byte
	ResponseID uint32
	Count      int
	Valid      bool
	VINs       []string
	Issues     []string
}

type Profile struct {
	VIN           string
	ECUCount      int
	HasCEM726     bool
	HasCEM29      bool
	ModelYear     int
	StrictRouting bool
	Advisories    []string
	Fixtures      []Fixture
	Issues        []string
}

func parseINI(input string) map[string]map[string]string {
	result := map[string]map[string]string{}
	current := ""
	s := bufio.NewScanner(strings.NewReader(input))
	s.Buffer(make([]byte, 4096), 2*1024*1024)
	for s.Scan() {
		line := strings.TrimSpace(s.Text())
		if line == "" || strings.HasPrefix(line, ";") || strings.HasPrefix(line, "#") {
			continue
		}
		if strings.HasPrefix(line, "[") && strings.HasSuffix(line, "]") {
			current = strings.ToUpper(strings.TrimSpace(line[1 : len(line)-1]))
			if result[current] == nil {
				result[current] = map[string]string{}
			}
			continue
		}
		if i := strings.IndexByte(line, '='); i > 0 && current != "" {
			result[current][strings.ToUpper(strings.TrimSpace(line[:i]))] = strings.TrimSpace(line[i+1:])
		}
	}
	return result
}

func parseID(value string) (uint32, error) {
	if value == "" {
		return 0, fmt.Errorf("не задан ResponseId")
	}
	n, e := strconv.ParseUint(strings.TrimPrefix(strings.ToUpper(value), "0X"), 16, 32)
	return uint32(n), e
}
func decode8(value string) ([]byte, error) {
	x := strings.NewReplacer(" ", "", "\t", "", "-", "", ":", "").Replace(value)
	if len(x) != 16 {
		return nil, fmt.Errorf("ожидалось ровно 8 байт, получено %d", len(x)/2)
	}
	return hex.DecodeString(x)
}
func frameKey(opcode byte, i int) string {
	if opcode == 0xFB {
		return fmt.Sprintf("B9FBFRAME%X", i)
	}
	return fmt.Sprintf("FRAME%X", i)
}
func validateVIN(s string) bool {
	return len(s) == 17 && vinToken.MatchString(s)
}

// modelYearCode checks only the VIN year-code syntax. For European cars,
// position 9 is not necessarily a North-American check digit.
func modelYearCode(year int) byte {
	const codes = "123456789ABCDEFGHJKLMNPRSTVWXY"
	if year < 2001 || year >= 2001+len(codes) {
		return 0
	}
	return codes[year-2001]
}

// ReadProfile checks the actual INI which the J2534 DLL will load.
// A valid fixture passes D2 transport checks only, not OEM identity validation.
func ReadProfile(input string) Profile {
	ini := parseINI(input)
	p := Profile{VIN: strings.ToUpper(ini["VEHICLE"]["VIN"])}
	p.StrictRouting = ini["P2"]["STRICTROUTING"] == "1"

	// Diagnostic route hints only; no ECU identity is inferred.
	countRaw := ini["VEHICLE"]["ECUCOUNT"]
	p.ECUCount = 2 // mirrors DLL default when ECUCount is absent
	if countRaw != "" {
		parsed, err := strconv.Atoi(countRaw)
		if err != nil || parsed < 1 || parsed > 8 {
			p.ECUCount = 1 // mirrors DLL fallback on invalid count
		} else {
			p.ECUCount = parsed
		}
	}
	for i := 0; i < p.ECUCount; i++ {
		sec := ini[fmt.Sprintf("ECU%d", i)]
		defaultID := uint32(0x7E0)
		if i == 1 { defaultID = 0x726 }
		id := defaultID
		if raw := sec["REQUESTID"]; raw != "" {
			if parsed, err := parseID(raw); err == nil { id = parsed }
		}
		if id == 0x726 { p.HasCEM726 = true }
		if id == 0x18DA50F1 { p.HasCEM29 = true }
	}
	if !validateVIN(p.VIN) {
		p.Issues = append(p.Issues, "VIN в [Vehicle] отсутствует либо не соответствует 17-символьному формату")
	}
	if raw := ini["VEHICLE"]["MODELYEAR"]; raw != "" {
		year, err := strconv.Atoi(raw)
		if err != nil || modelYearCode(year) == 0 {
			p.Issues = append(p.Issues, "ModelYear должен быть годом в диапазоне 2001–2030")
		} else {
			p.ModelYear = year
			if validateVIN(p.VIN) && p.VIN[9] != modelYearCode(year) {
				p.Issues = append(p.Issues, fmt.Sprintf("VIN: код модельного года не совпадает с ModelYear=%d", year))
			}
		}
	}
	if provenance := ini["P2"]["FIXTUREPROVENANCE"]; provenance != "" {
		p.Advisories = append(p.Advisories, "Происхождение P2: "+provenance+"; это описание источника, не OEM-верификация")
	}
	for _, spec := range []struct {
		name           string
		target, opcode byte
	}{
		{"D2_40", 0x40, 0xFB}, {"D2_40_B9F0", 0x40, 0xF0},
		{"D2_50", 0x50, 0xFB}, {"D2_50_B9F0", 0x50, 0xF0},
		{"D2_40_B9FC", 0x40, 0xFC}, {"D2_50_B9FC", 0x50, 0xFC},
	} {
		section := ini[spec.name]
		f := Fixture{Name: spec.name, Target: spec.target, Opcode: spec.opcode, Valid: true}
		if section == nil {
			p.Fixtures = append(p.Fixtures, f)
			continue
		}
		id, iderr := parseID(section["RESPONSEID"])
		f.ResponseID = id
		countKey := "FRAMECOUNT"
		if spec.opcode == 0xFB && section[countKey] == "" {
			countKey = "B9FBFRAMECOUNT"
		}
		count, err := strconv.Atoi(section[countKey])
		if section[countKey] == "" {
			count = 0
			err = nil
		}
		if err != nil || count < 0 || count > 64 {
			f.Issues = append(f.Issues, "число кадров должно быть от 0 до 64")
		} else {
			f.Count = count
		}
		if f.Count > 0 {
			if iderr != nil || id > 0x1FFFFFFF || id == 0 {
				f.Issues = append(f.Issues, "некорректный 29-битный ResponseId")
			}
			frames := make([][]byte, 0, f.Count)
			for i := 0; i < f.Count; i++ {
				value := section[frameKey(spec.opcode, i)]
				if value == "" {
					value = section[fmt.Sprintf("FRAME%X", i)]
				}
				b, e := decode8(value)
				if e != nil {
					f.Issues = append(f.Issues, fmt.Sprintf("кадр %X: %v", i, e))
					break
				}
				frames = append(frames, b)
			}
			if len(frames) == f.Count {
				if fault := checkFrameSequence(frames, spec.target, spec.opcode); fault != "" {
					f.Issues = append(f.Issues, fault)
				}
				if spec.opcode == 0xFC {
					payload, err := decodeFC140Frames(frames, spec.target)
					if err != nil {
						f.Issues = append(f.Issues, "B9FC: "+err.Error())
					} else {
						f.Advisories = append(f.Advisories, fmt.Sprintf("B9FC: проверено 140 значений, checksum 0x%02X; идентичность и CAN ID B9FC не подтверждены", payload[1]))
					}
				}
				if spec.opcode == 0xFB {
					payload := make([]byte, 0, 7*len(frames))
					for _, frame := range frames {
						payload = append(payload, frame[1:]...)
					}
					// The provenance marker is a literal text fragment in
					// the historical response. Its OEM field meaning is unknown.
					if strings.Contains(string(payload), "200512") {
						f.Advisories = append(f.Advisories, "найден фрагмент 200512 из исторической записи; значение поля не расшифровано и не проверено для текущего VIN")
					}
					candidates := vinToken.FindAllString(string(payload), -1)
					for _, v := range candidates {
						f.VINs = append(f.VINs, v)
					}
					if len(f.VINs) == 0 {
						f.Issues = append(f.Issues, "VIN не найден в ответе B9FB (возможна маскировка или иной формат)")
					}
					if len(f.VINs) > 1 {
						f.Issues = append(f.Issues, "обнаружено несколько VIN-подобных фрагментов, проверьте структуру")
					}
					if len(f.VINs) == 1 && validateVIN(p.VIN) && f.VINs[0] != p.VIN {
						f.Issues = append(f.Issues, "VIN из B9FB не совпадает с VIN из [Vehicle]")
					}
				}
			}
		}
		f.Valid = len(f.Issues) == 0
		p.Fixtures = append(p.Fixtures, f)
	}
	return p
}

// decodeFC140Frames validates the *observed* 140-byte configuration format.
// The 29-bit response ID cannot be inferred from the Flash file alone.
func decodeFC140Frames(frames [][]byte, target byte) ([]byte, error) {
	if len(frames) != 21 || frames[0][0] != 0x8F || frames[20][0] != 0x4D {
		return nil, fmt.Errorf("ожидается 21 кадр, первый 8F, последний 4D")
	}
	stream := make([]byte, 0, 145)
	for i, frame := range frames {
		end := 8
		if i == 20 {
			end = 6
		}
		stream = append(stream, frame[1:end]...)
	}
	if len(stream) != 145 || stream[0] != target || stream[1] != 0xF9 || stream[2] != 0xFC || stream[3] != 0x8C {
		return nil, fmt.Errorf("неверный формат данных FC140")
	}
	block := stream[3:]
	var sum byte
	for _, v := range block[2:] {
		sum += v
	}
	if sum != block[1] {
		return nil, fmt.Errorf("неверный контрольный байт FC140")
	}
	return block, nil
}

// checkFrameSequence validates only the recorded D2 transport. It accepts
// 0x08-series and 0x10-series, intermediate 0x5x and duplicated 0x8F after 0x5x.
func checkFrameSequence(frames [][]byte, target, opcode byte) string {
	if len(frames) == 0 {
		return ""
	}
	if len(frames) == 1 {
		f := frames[0]
		if (f[0]&0xF8) != 0xC8 || f[1] != target ||
			!((f[2] == 0xF9 && f[3] == opcode) || (f[2] == 0x7F && f[3] == 0xB9)) {
			return "неверный однокадровый ответ D2"
		}
		return ""
	}
	first := frames[0]
	if (first[0] != 0x8F && first[0] != 0x97) || first[1] != target || first[2] != 0xF9 || first[3] != opcode {
		return "неверный первый кадр D2 (ожидался 8F либо 97 с корректным эхом)"
	}
	base := byte(0x08)
	if first[0]&0x10 != 0 {
		base = 0x10
	}
	seq := byte(1)
	for i := 1; i < len(frames); i++ {
		h := frames[i][0]
		if h >= 0x48 && h <= 0x4F {
			if i != len(frames)-1 {
				return fmt.Sprintf("ранний завершающий кадр D2 %d", i)
			}
			if base == 0x08 && len(frames) == 13 && h != 0x4F {
				return "известная 13-кадровая запись должна завершаться 4F"
			}
			return ""
		}
		if (h & 0xF8) == 0x50 {
			if i == len(frames)-1 {
				return "промежуточный подблок 5x не завершает ответ"
			}
			continue
		}
		if h == 0x8F && i > 1 && (frames[i-1][0]&0xF8) == 0x50 &&
			frames[i][1] == target && frames[i][2] == 0xF9 && frames[i][3] == opcode {
			continue
		}
		if h != (base | seq) {
			return fmt.Sprintf("ошибка последовательности D2 в кадре %d", i)
		}
		seq = (seq + 1) & 7
	}
	return "нет завершающего кадра 4x"
}

func redactVIN(s string) string {
	if len(s) != 17 {
		return "(не найден)"
	}
	return s[:3] + "**********" + s[13:]
}
func (p Profile) Report() string {
	var b strings.Builder
	b.WriteString("АУДИТ P2 CEM (только чтение)\n")
	fmt.Fprintf(&b, "VIN [Vehicle]: %s\n", redactVIN(p.VIN))

	fmt.Fprintf(&b, "Смоделированных UDS ECU: %d\n", p.ECUCount)
	if !p.HasCEM726 {
		b.WriteString("МАРШРУТ 0x726: не настроен; запросы CEM F114 по CAN 11-bit останутся без ответа.\n")
	} else {
		b.WriteString("МАРШРУТ 0x726: настроен; точность ответа CEM требует отдельной проверки.\n")
	}
	if !p.HasCEM29 {
		b.WriteString("МАРШРУТ 0x18DA50F1: не настроен; запросы CEM F110/F114/F106 по CAN 29-bit останутся без ответа.\n")
	} else {
		b.WriteString("МАРШРУТ 0x18DA50F1: настроен; поддержку конкретных DID необходимо проверять отдельно.\n")
	}
	b.WriteString("ОГРАНИЧЕНИЕ DLL dev28: D2 A3/A6 и B9D0 не обрабатываются, наличие донорского B9FB это не исправляет.\n")
	for _, issue := range p.Issues {
		fmt.Fprintf(&b, "ВНИМАНИЕ: %s\n", issue)
	}
	if p.StrictRouting {
		b.WriteString("Маршрутизация P2: строгая (0x40 / 125 кбит/с, 0x50 / 500 кбит/с)\n")
	}
	if p.ModelYear != 0 {
		fmt.Fprintf(&b, "ModelYear: %d (сравнен с 10-м символом VIN, без проверки регистрационного рынка)\n", p.ModelYear)
	}
	for _, a := range p.Advisories {
		fmt.Fprintf(&b, "ПРИМЕЧАНИЕ: %s\n", a)
	}
	for _, f := range p.Fixtures {
		fmt.Fprintf(&b, "\n%s, CEM 0x%02X, B9%02X: ", f.Name, f.Target, f.Opcode)
		if f.Count == 0 {
			b.WriteString("ответ не настроен\n")
			for _, issue := range f.Issues {
				fmt.Fprintf(&b, "  ВНИМАНИЕ: %s\n", issue)
			}
			continue
		}
		fmt.Fprintf(&b, "%d кадров, RX CAN 0x%08X\n", f.Count, f.ResponseID)
		for _, v := range f.VINs {
			fmt.Fprintf(&b, "  VIN в записи: %s\n", redactVIN(v))
		}
		if f.Valid {
			b.WriteString("  D2 последовательность: корректна\n")
		}
		for _, issue := range f.Issues {
			fmt.Fprintf(&b, "  ВНИМАНИЕ: %s\n", issue)
		}
		for _, a := range f.Advisories {
			fmt.Fprintf(&b, "  ПРИМЕЧАНИЕ: %s\n", a)
		}
	}
	b.WriteString("\nВажное ограничение: корректная последовательность D2 и совпадающий VIN не подтверждают\n")
	b.WriteString("подлинность остальных полей, контрольных сумм или принятие автомобиля SectorV.\n")
	return b.String()
}

// D2Replay is one B9FB request and the J2534 deliveries attributed to it.
// It verifies the transport order; it does not evaluate proprietary OEM fields.
type D2Replay struct {
	Frames       int
	Complete     bool
	SequenceOK   bool
	Fault        string
	ClosedAfter  bool
	Base         byte
	Next         byte
	PrevSubblock bool
}

// LogSummary summarizes the most recent user-marked attempt, or the most
// recent host process when the user did not mark a session.
type LogSummary struct {
	Entries, Requests40, Requests50, Delivered50, Missing40, Missing50, Staged50 int
	ResetBroadcasts, MetadataEvents                                              int
	Requests40LS, Requests40HS, Requests50LS, Requests50HS                       int
	LastProcess                                                                  string
	Complete50, ClosedAfter50                                                    bool
	Replays50                                                                    []D2Replay
}

// parseLogBytes returns only complete hexadecimal byte fields from the
// trailing text of a J2534 diagnostic log entry.
func parseLogBytes(line, prefix string, count int) ([]byte, bool) {
	idx := strings.Index(line, prefix)
	if idx < 0 {
		return nil, false
	}
	fields := strings.Fields(line[idx+len(prefix):])
	if len(fields) < count {
		return nil, false
	}
	result := make([]byte, count)
	for i := 0; i < count; i++ {
		if len(fields[i]) != 2 {
			return nil, false
		}
		value, err := strconv.ParseUint(fields[i], 16, 8)
		if err != nil {
			return nil, false
		}
		result[i] = byte(value)
	}
	return result, true
}
func logBE32(data []byte) uint32 {
	return uint32(data[0])<<24 | uint32(data[1])<<16 | uint32(data[2])<<8 | uint32(data[3])
}
func countBusRequest(s *LogSummary, target byte, baud uint32) {
	switch {
	case target == 0x40 && baud == 125000:
		s.Requests40LS++
	case target == 0x40 && baud == 500000:
		s.Requests40HS++
	case target == 0x50 && baud == 125000:
		s.Requests50LS++
	case target == 0x50 && baud == 500000:
		s.Requests50HS++
	}
}

func SummarizeLog(content string) LogSummary {
	lines := strings.Split(strings.ReplaceAll(content, "\r\n", "\n"), "\n")
	selected := lines
	marked := false
	for i, line := range lines {
		if strings.HasPrefix(line, "=== SECTORV VIRTUALCAR SESSION ") {
			selected = lines[i+1:]
			marked = true
		}
	}
	if !marked {
		latest := ""
		// The last SectorV process in the log is normally the latest attempt.
		// Preserve ALL its re-openings, but never mix different PIDs/versions.
		for _, line := range lines {
			if strings.Contains(line, " SectorV.exe]") && strings.HasPrefix(line, "[PID=") && len(line) >= 13 {
				latest = line[5:13]
			}
		}
		if latest != "" {
			prefix := "[PID=" + latest + " SectorV.exe]"
			filtered := []string{}
			for _, line := range lines {
				if strings.HasPrefix(line, prefix) {
					filtered = append(filtered, line)
				}
			}
			selected = filtered
		}
	}
	s := LogSummary{}
	legacy := LogSummary{}
	var activeBaud uint32
	lastB9FBIndex := -1
	var current *D2Replay
	finishReplay := func() {
		if current != nil {
			s.Replays50 = append(s.Replays50, *current)
			current = nil
		}
	}
	for i, line := range selected {
		if !strings.Contains(line, " SectorV.exe]") {
			continue
		}
		s.Entries++
		if b, ok := parseLogBytes(line, "PassThruConnect protocol / flags / baud (BE) ", 12); ok {
			activeBaud = logBE32(b[8:12])
		}
		if b, ok := parseLogBytes(line, "P2 D2 request target/opcode/baud/flags (BE) ", 16); ok {
			s.MetadataEvents++
			if logBE32(b[4:8]) == 0xFB {
				countBusRequest(&s, byte(logBE32(b[:4])), logBE32(b[8:12]))
			}
		}
		if s.LastProcess == "" && len(line) >= 13 {
			s.LastProcess = line[5:13]
		}
		if strings.Contains(line, "TX (app request) 00 0F FF FE CB 40 B9 FB") {
			s.Requests40++
			countBusRequest(&legacy, 0x40, activeBaud)
		}
		if strings.Contains(line, "TX (app request) 00 0F FF FE CB 50 B9 FB") {
			s.Requests50++
			countBusRequest(&legacy, 0x50, activeBaud)
			finishReplay()
			lastB9FBIndex = i
			current = &D2Replay{SequenceOK: true}
		}
		if strings.Contains(line, "P2 D2 read command: no validated response fixture CB 40 B9 FB") {
			s.Missing40++
		}
		if strings.Contains(line, "P2 D2 read command: no validated response fixture CB 50 B9 FB") {
			s.Missing50++
		}
		if strings.Contains(line, "P2 D2 read-only recorded frames staged CB 50 B9 FB") {
			s.Staged50++
		}
		if strings.Contains(line, "PassThruReadMsgs -> delivered 01 20 00 03") {
			s.Delivered50++
			if current != nil {
				frame, ok := parseLogBytes(line, "PassThruReadMsgs -> delivered ", 12)
				if !ok {
					current.SequenceOK = false
					current.Fault = "некорректный размер или формат RX кадра"
				} else {
					payload := frame[4:]
					index := current.Frames
					wasComplete := current.Complete
					switch {
					case wasComplete:
						current.SequenceOK = false
						current.Complete = false
						current.Fault = "кадр после завершения D2"
					case index == 0:
						if (payload[0] != 0x8F && payload[0] != 0x97) || payload[1] != 0x50 || payload[2] != 0xF9 || payload[3] != 0xFB {
							current.SequenceOK = false
							current.Fault = "неверный первый кадр 8F/97 50 F9 FB"
						} else {
							current.Base = 0x08
							if payload[0] == 0x97 {
								current.Base = 0x10
							}
							current.Next = 1
						}
					case payload[0] >= 0x48 && payload[0] <= 0x4F:
						if index == 12 && current.Base == 0x08 && payload[0] != 0x4F {
							current.SequenceOK = false
							current.Fault = "неверный завершающий кадр известной 13-кадровой записи"
						}
						current.Complete = current.SequenceOK
					case (payload[0] & 0xF8) == 0x50:
						current.PrevSubblock = true
					case payload[0] == 0x8F && current.PrevSubblock && payload[1] == 0x50 && payload[2] == 0xF9 && payload[3] == 0xFB:
						current.PrevSubblock = false
					case payload[0] != (current.Base | current.Next):
						current.SequenceOK = false
						current.Fault = fmt.Sprintf("разрыв D2 последовательности на кадре %d", index)
					default:
						current.Next = (current.Next + 1) & 7
						current.PrevSubblock = false
					}
				}
				current.Frames++
				if current.Frames > 64 {
					current.SequenceOK = false
					current.Complete = false
					current.Fault = "более 64 кадров в одном ответе"
				}
			}
		}
		if current != nil && strings.Contains(line, "PassThruClose") {
			current.ClosedAfter = true
		}
		// Count the application command, not the DLL commentary. In real
		// P2 traces FF C8 is used as a broadcast ECU reset, not discovery.
		if strings.Contains(line, "TX (app request) 00 0F FF FE FF C8") {
			s.ResetBroadcasts++
		}
	}
	if s.MetadataEvents == 0 {
		// Backward compatibility with 0.3.1/0.3.2 logs. Sequential channel
		// inference is not reliable for parallel J2534 channels.
		s.Requests40LS, s.Requests40HS = legacy.Requests40LS, legacy.Requests40HS
		s.Requests50LS, s.Requests50HS = legacy.Requests50LS, legacy.Requests50HS
	}
	finishReplay()
	// Transport acceptance requires a valid start, ordered consecutive
	// frames and an end-of-message. Counts alone are insufficient.
	if n := len(s.Replays50); n > 0 {
		s.Complete50 = s.Replays50[n-1].Complete && s.Replays50[n-1].SequenceOK
	}
	if lastB9FBIndex >= 0 {
		for _, line := range selected[lastB9FBIndex+1:] {
			if strings.Contains(line, " SectorV.exe]") && strings.Contains(line, "PassThruClose") {
				s.ClosedAfter50 = true
				break
			}
		}
	}
	return s
}
func (s LogSummary) Report() string {
	var b strings.Builder
	b.WriteString("ПОСЛЕДНЯЯ ОТМЕЧЕННАЯ СЕССИЯ / ПОСЛЕДНИЙ PID SectorV\n")
	if s.LastProcess != "" {
		fmt.Fprintf(&b, "PID: %s\n", s.LastProcess)
	}
	fmt.Fprintf(&b, "Строк SectorV: %d\n", s.Entries)
	fmt.Fprintf(&b, "CEM 0x40 B9FB: запросов %d, без ответа %d\n", s.Requests40, s.Missing40)
	fmt.Fprintf(&b, "CEM 0x50 B9FB: запросов %d, запусков записи %d, доставлено кадров 0x01200003: %d\n", s.Requests50, s.Staged50, s.Delivered50)
	fmt.Fprintf(&b, "  CAN-LS 125 кбит/с: 0x40=%d, 0x50=%d\n", s.Requests40LS, s.Requests50LS)
	fmt.Fprintf(&b, "  CAN-HS 500 кбит/с: 0x40=%d, 0x50=%d\n", s.Requests40HS, s.Requests50HS)
	if s.MetadataEvents == 0 && (s.Requests40+s.Requests50 > 0) {
		b.WriteString("Скорость восстановлена по последнему PassThruConnect: для параллельных каналов возможна неточность.\n")
	}
	fmt.Fprintf(&b, "FF C8: широковещательный запрос сброса ECU, отправлений %d; виртуальный адаптер не отвечает (ожидаемо).\n", s.ResetBroadcasts)
	b.WriteString("CEM 0x40 на CAN-LS может молчать при поиске P2 MY2005+, это не доказательство ошибки.\n")
	if len(s.Replays50) > 0 {
		fmt.Fprintf(&b, "Разобрано ответов B9FB 0x50: %d\n", len(s.Replays50))
		for i, item := range s.Replays50 {
			if i < len(s.Replays50)-5 {
				continue
			}
			if item.Frames == 0 {
				fmt.Fprintf(&b, "  Попытка %d: 0 доставленных кадров, транспорт D2 не начинался\n", i+1)
				if s.Missing50 > 0 {
					b.WriteString("    DLL сообщает об отсутствии настроенного ответа B9FB.\n")
				} else {
					b.WriteString("    По журналу нельзя отличить отсутствие ответа от потери RX/фильтрации.\n")
				}
				continue
			}
			result := "неполный или с ошибкой"
			if item.Complete && item.SequenceOK {
				result = fmt.Sprintf("%d кадров, порядок D2 корректен", item.Frames)
			}
			fmt.Fprintf(&b, "  Ответ %d: %s (получено %d)\n", i+1, result, item.Frames)
			if item.Fault != "" {
				fmt.Fprintf(&b, "    Причина: %s\n", item.Fault)
			}
			if !item.Complete && item.Fault == "" {
				b.WriteString("    Нет подтверждённого завершающего кадра D2.\n")
			}
		}
	}
	if s.Complete50 {
		b.WriteString("Последний B9FB 0x50: последовательность D2 подтверждена по СОДЕРЖИМОМУ RX, не только по счётчику.\n")
	}
	if s.ClosedAfter50 {
		b.WriteString("После B9FB был PassThruClose. Это НЕ подтверждает принятие VIN.\n")
	}
	if s.Entries == 0 {
		b.WriteString("Нет записей SectorV. Начните новую сессию (кнопка 9) и повторите обнаружение.\n")
	}
	return b.String()
}
