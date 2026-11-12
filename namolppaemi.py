"""나몰빼미 데스크톱 마스코트 (시메지 스타일)

- 화면 바닥(작업 표시줄 위)을 걷고, 쉬고, 자고, 날아다닙니다.
- 집은 화면 왼쪽 아래 바닥의 몬스터볼로 고정. 마우스로 옮기면 그 주변에서
  잠시 놀다가 볼로 날아 돌아옵니다.
  설정에서 '자유롭게 돌아다니기'를 켜면 화면 전체를 돌아다닙니다.
- 왼쪽 드래그로 집어서 던질 수 있습니다. 클릭하면 말을 겁니다.
- 열린 앱 창의 윗변에 착지하거나 날아가 내려앉고, 창을 옮기면 같이 움직입니다.
- 우클릭: 상태 카드 (수치, 오늘 정보, 밥 주기·놀아주기·재우기(25분 뽀모도로) 버튼,
  '일정·업무' 메뉴(일정, 할 일, 브리핑, 날씨, 할 일 빠른 추가, 클로드에게 묻기),
  '설정·기타' 메뉴(움직임·알림·브리핑·연결 설정, 날아다니기, 집으로 돌아가기, 종료))
- 몬스터볼(왼쪽 아래 바닥, 나몰빼미의 둥지): 나몰빼미가 앉으면 몸 아래쪽이 볼의 흰 부분에 가려짐.
  친밀도 Lv.10마다 몬스터볼 → 슈퍼볼 → 하이퍼볼 → 마스터볼 → 프리미어볼 (BALL_TIERS).
  재우기(25분)를 시작하거나 빈 볼을 누르면 빨려 들어가 자고, 끝나거나 깨우면 튀어나옴.
  퇴근 종료 예고 중에도 들어가 있다가 마우스를 건드리면 나옴
- 어디서든 단축키: Ctrl+Alt+N 할 일 빠른 추가 (Notion TODO), Ctrl+Alt+K 클로드에게 묻기
- 출근 인사(아침 첫 입력), 퇴근 전 마무리 요약(평일 18시), 쉬지 않고 오래 일하면 스트레칭 알림,
  Claude Code 작업 상태 표시·알림, 18:30 이후 자리를 비우면 PC 자동 종료
- 다마고치: 배부름/기분이 시간이 지나면 줄고, 밥·쓰다듬기(놀아주기, 클릭)로 올라감.
  돌봐줄수록 친밀도 레벨이 오르고, 상태는 save.json 에 저장됨.
  밥그릇의 열매는 마우스로 집어 던질 수 있음.

실행:  pythonw namolppaemi.py        (콘솔 창 없이. run_namolppaemi.bat 이 이걸 실행함)

그림: character.png (기본), character_sleep / _hungry / _grumpy.png (모습별).
character.json 에 눈 위치를 적어 두면 깜빡이기/자기 표정이 그림 위에 덧그려집니다.

파일 구성 (수정할 때 찾아가기 편하게 나눠 둠):
  namolppaemi.py        이 파일. 시작점만 있음
  mascot/constants.py   숫자·간격·경로·말 모음 같은 설정 상수
  mascot/species.py     포켓몬 정의 (pokemon 폴더 읽기), 볼 단계
  mascot/winapi.py      Windows 창·모니터·단축키 도구
  mascot/notion.py, google_calendar.py, mail.py, slack.py, weather.py, holidays.py   바깥 서비스 연결
  mascot/ui.py          창 색감·날짜 위젯,  sprites.py 날개·열매,  secrets_store.py 토큰 암호화 저장
  mascot/pet/core.py    본체 Rowlet (처음 만들 때 수치와 창을 만듦)
  mascot/pet/*.py       기능별 조각: character(그림 불러오기) tamagotchi(수치) status_card(상태 카드)
                        agenda(일정) notion_ui(할 일) notifications(메일·Slack) routines(날씨·포즈)
                        ball_home(집·볼) roaming(돌아다니기) main_loop(매 틱 움직임) pomodoro(재우기)
                        pokedex(도감) daily_report(일일 업무) input_events(마우스·메뉴) bubble(말풍선) drawing(그리기) 등
"""
from mascot.pet import Rowlet
from mascot.single_instance import already_running


if __name__ == "__main__":
    if not already_running():
        Rowlet().run()
