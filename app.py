import streamlit as st
import json
import httpx
from openai import OpenAI

# --- 1. 基本設定 ---

st.set_page_config(page_title="AI問診アシスタント", layout="wide")

st.title("🩺 AI問診アシスタント (高機能版)")
st.write(
    "AIとの対話を通じて、あなたの症状から考えられる病気の可能性を探ります。"
    "あなたの回答に合わせてAIが質問を生成します。"
)

st.warning(
    "**免責事項:** 本サービスは医療診断ではありません。あくまで情報提供を目的としており、医師の診断に代わるものではありません。"
    "正確な診断と治療については、必ず医療機関を受診してください。"
)

# --- 2. OpenAIクライアントの初期化 ---

st.sidebar.header("設定")
# サイドバーでユーザーにAPIキーを入力してもらう
api_key = st.sidebar.text_input(
    "あなたのOpenAI APIキーを入力してください",
    type="password",
    help="APIキーはこのブラウザセッションでのみ使用され、サーバーには保存されません。"
)

# APIキーが入力されているかチェックし、クライアントを初期化
if api_key:
    try:
        custom_http_client = httpx.Client(timeout=30.0)
        client = OpenAI(
            api_key=api_key,
            http_client=custom_http_client
        )
    except Exception as e:
        st.error(f"OpenAIクライアントの初期化中にエラーが発生しました: {e}")
        st.stop()
else:
    # APIキーが入力されていない場合は、メッセージを表示して処理を中断
    st.info("サイドバーにあなたのOpenAI APIキーを入力すると、問診を開始できます。")
    st.stop()


# --- 3. 状態管理 (Session State) ---

# セッション状態の初期化
if "page" not in st.session_state:
    st.session_state.page = "start"
if "messages" not in st.session_state:
    st.session_state.messages = []
if "diagnosis_result" not in st.session_state:
    st.session_state.diagnosis_result = None
if "report_cache" not in st.session_state:
    st.session_state.report_cache = {}


# --- 4. AIとのやり取りを行う関数 ---

def get_ai_response(prompt, response_format="json"):
    """汎用的なAI呼び出し関数"""
    # APIに渡すために、会話履歴を整形する
    formatted_messages = []
    for msg in st.session_state.messages:
        role = msg["role"]
        content_data = msg["content"]
        
        # content の形式に応じて整形する
        if role == "assistant":
            # アシスタントの content は辞書なので、質問文のテキストだけを取り出す
            content_text = content_data.get("question", "")
        else:  # role == "user"
            # ユーザーの content は文字列なので、そのまま使う
            content_text = content_data
            
        formatted_messages.append({"role": role, "content": content_text})

    # 整形済みのメッセージリストをAPIに渡す
    messages_for_api = [
        {"role": "system", "content": prompt}
    ] + formatted_messages

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages_for_api,
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        content = response.choices[0].message.content
        return json.loads(content)
    except Exception as e:
        st.error(f"AIとの通信中にエラーが発生しました: {e}")
        return None

def generate_detailed_report(disease_name):
    """特定の病気に関する詳細レポートを生成する"""
    if disease_name in st.session_state.report_cache:
        return st.session_state.report_cache[disease_name]

    with st.spinner(f"「{disease_name}」の詳細レポートを生成中..."):
        prompt = f"""
あなたは優秀な医療情報アシスタントです。ただし、医師の診断を代替するものではありません。
以下の指示に従って、ユーザー向けの分かりやすいレポートを作成してください。

病名: {disease_name}

レポートに含める項目:
1. どのような病気かの簡単な説明
2. 一般的な症状（特に今回の問診内容と関連する症状を強調）
3. 自宅でできる対処法（セルフケア）
4. どのような場合に病院に行くべきか（受診の目安となる具体的な症状や期間）
5. 推奨される診療科

**重要:** レポートの冒頭と末尾に、この情報が医師の診断に代わるものではなく、あくまで一般的な情報提供であり、最終的な判断は医療機関に相談すべきである旨を明確に記載してください。
"""
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": prompt}
                ],
                temperature=0.5,
            )
            report_content = response.choices[0].message.content
            st.session_state.report_cache[disease_name] = report_content
            return report_content
        except Exception as e:
            st.error(f"レポート生成中にエラーが発生しました: {e}")
            return None


# --- 5. UIの描画 ---

# リセットボタン
if st.sidebar.button("最初からやり直す"):
    # セッション状態をクリアしてリロード
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

st.divider()

# ページに応じた表示の切り替え
# ------------------ スタートページ ------------------
if st.session_state.page == "start":
    st.header("問診を開始します")
    first_symptom = st.text_input("はじめに、最も気になる症状を具体的に教えてください。（例：3日前から続く、喉の痛みと38度の熱）", key="first_symptom_input")
    if st.button("問診を始める", disabled=not first_symptom):
        # 最初のユーザー入力をメッセージ履歴に追加
        st.session_state.messages.append({"role": "user", "content": first_symptom})
        st.session_state.page = "chat"
        st.rerun()

# ------------------ チャット（問診）ページ ------------------
elif st.session_state.page == "chat":
    st.header("AIによる問診")
    
    # まず、これまでの会話履歴をすべて表示する
    for msg_data in st.session_state.messages:
        role = msg_data["role"]
        if role == "assistant":
            content = msg_data.get("content", {}).get("question", "エラー：内容を取得できませんでした")
        else:
            content = msg_data.get("content")

        with st.chat_message(role):
            st.write(content)

    # 履歴の最後のメッセージがAIからのもので、かつ未回答の場合に選択肢を表示する
    if st.session_state.messages and st.session_state.messages[-1]["role"] == "assistant":
        last_ai_msg = st.session_state.messages[-1].get("content", {})
        is_final = last_ai_msg.get("is_final", False)
        options = last_ai_msg.get("options")

        if not is_final and options:
            button_container = st.container()
            cols = button_container.columns(len(options))
            for i, option in enumerate(options):
                if cols[i].button(option, key=f"option_{len(st.session_state.messages)}_{i}"):
                    # ユーザーの回答を履歴に追加
                    st.session_state.messages.append({"role": "user", "content": option})
                    st.rerun()
        elif is_final:
            if st.button("診断結果へ進む"):
                st.session_state.page = "result"
                st.rerun()

    # 履歴が空、または最後のメッセージがユーザーからのものなら、AIの番
    elif not st.session_state.messages or st.session_state.messages[-1]["role"] == "user":
        prompt_for_question = """
あなたは経験豊富な問診医です。提供された問診履歴に基づき、症状を特定するために最も効果的な次の質問を1つ生成してください。
- 質問は簡潔で分かりやすくしてください。
- 回答しやすいように、3〜5個の具体的な選択肢を付けてください。
- ユーザーが判断に迷う場合に備え、「分からない」「当てはまらない」といった選択肢も適宜含めてください。
- 十分な情報が集まったと判断した場合は、`is_final`を`true`に設定し、質問の代わりに診断に移ることを促すメッセージを`question`に入れてください。
- 必ず以下のJSON形式で回答してください。
{
    "question": "（ここに質問文）",
    "options": ["選択肢1", "選択肢2", "選択肢3", "..."],
    "is_final": false
}
"""
        with st.chat_message("assistant"):
            with st.spinner("AIが次の質問を考えています..."):
                ai_response = get_ai_response(prompt_for_question)
                if ai_response:
                    st.session_state.messages.append({"role": "assistant", "content": ai_response})
                    st.rerun()

    # 診断に進むボタン（いつでも押せるように）
    if len(st.session_state.messages) >= 3:
        if st.button("ここまでの情報で診断結果を見る"):
            st.session_state.page = "result"
            st.rerun()


# ------------------ 結果ページ ------------------
elif st.session_state.page == "result":
    st.header("問診結果")

    if not st.session_state.diagnosis_result:
        with st.spinner("AIが問診内容を分析し、可能性のある病名を検討しています..."):
            prompt_for_diagnosis = """
あなたは優秀な医療AIアシスタントです。提供された問診履歴を総合的に分析し、考えられる病名を可能性の高い順に3つまで挙げてください。
- 各病名について、なぜその可能性が考えられるのか簡単な根拠を`reason`に記述してください。
- 可能性の度合いを`likelihood`として「高」「中」「低」で示してください。
- 必ず以下のJSON形式で回答してください。
{
  "diagnoses": [
    {
      "name": "（病名1）",
      "likelihood": "高",
      "reason": "（根拠）"
    },
    {
      "name": "（病名2）",
      "likelihood": "中",
      "reason": "（根拠）"
    }
  ]
}
"""
            diagnosis_result = get_ai_response(prompt_for_diagnosis)
            if diagnosis_result:
                st.session_state.diagnosis_result = diagnosis_result.get("diagnoses", [])

    if st.session_state.diagnosis_result:
        st.subheader("考えられる病気の可能性")
        for diagnosis in st.session_state.diagnosis_result:
            with st.expander(f"**{diagnosis['name']}** (可能性: {diagnosis['likelihood']})"):
                st.write(f"**考えられる理由:** {diagnosis['reason']}")
                if st.button(f"「{diagnosis['name']}」の詳細レポートを見る", key=f"report_{diagnosis['name']}"):
                    report = generate_detailed_report(diagnosis['name'])
                    if report:
                        st.markdown(report)
    else:
        st.error("診断結果の生成に失敗しました。APIキーが正しいか確認後、再度お試しください。")

    with st.expander("今回の問診の全履歴を見る"):
        for msg in st.session_state.messages:
            role = msg["role"]
            if role == "assistant":
                content = msg.get("content", {}).get("question", "...")
                st.text(f"AI: {content}")
            else:
                content = msg.get("content")
                st.text(f"あなた: {content}")