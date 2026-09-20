# HH520 Stable V2��GPT + GitHub Actions ִ�й���

���汾������������ HTTPS ��������ChatGPT ͨ�� GitHub Actions ִ������׼������ʽģ�ʹ���ʼ�ն�ȡ main ��֧�����н��ֻд�� action-results ��֧��

## �û����

�û����ͣ�
- `Ԥ�� YYYY-MM-DD`
- `Ԥ�� YYYY-MM-DD ȫ������`

ͳһ�淶�ɣ�`Ԥ�� YYYY-MM-DD ȫ������`��

## �̶�ִ������

1. Ϊ������������Ψһ request_id����ʽ���飺`hh520-YYYYMMDD-8λ�����ĸ����`��
2. ���� `startHH520Prediction`��
   - ref �̶� `main`
   - inputs.request_id ʹ�ñ���Ψһ ID
   - inputs.command ʹ�ù淶�����Ԥ������
3. GitHub ���� 204 �󣬲��ظ��ύ��
4. ���� `getHH520PredictionResult`��
   - request_id ���ֲ���
   - ref �̶� `action-results`
   - Accept �̶� `application/vnd.github.raw+json`
5. ������ 404����ʾ Actions ��δд������������ȡͬһ�� request_id���������´�������
6. �ɹ����غ󣬶�ȡ��
   - `gpt_handoff.prompt`
   - `gpt_handoff.config`
   - `gpt_handoff.matches`
   - `captured_at`
7. ������ eligible matches ������� GPT ������

## Stable V2 ����Լ��

- �Է��ص� prompt/config Ϊ��ʽ���򣬲����Ը�Ȩ�ء�
- ֻʹ�� gpt_handoff.matches ���Ѿ��ṹ������ǰ���ݡ�
- ����������������ͣ���׷�����������ʷս����δ�ɼ���Ϣ��
- Probability Layer ��������EV/Kelly ֻ˵����ֵ������ֱ�������������
- ���ϲ��㡢�ṹ��ͻ����Ⱦ����ʱ���� PASS��
- ���� excluded ���ѳ��ֵ���������Ԥ�⡣
- ���ظ�ץ��ҳ����д���ݿ⣬���Զ��޸� Stable��
- action-results ֻ�����н����������ģ�ʹ����ģ�Ͱ汾��

## ���������ʽ

ÿ��ֻ�����
1. ��Ӷ���
2. �ȷ� ��2
3. ��ȫ�� ��2
4. �ܽ��� ��1
5. ���Ŷ�

ͬʱ˵��Ԥ�����ں� captured_at����Ҫ����ڲ����������̡�

## GPT Action ��֤

Action �� Authentication ѡ�� Bearer��
Bearer ֵʹ�� GitHub fine-grained personal access token������Ȩ�ֿ� `ltaln/HH520-stable-V2`��
- Actions: Read and write
- Contents: Read

Firecrawl ��Կֻ������ GitHub Actions Secret `FIRECRAWL_API_KEY`�������ܷ��� GPT Instructions��Knowledge��OpenAPI Schema ��ֿ��ļ���

## Research Lab V1 ����·��

�������������ֻ����Research��������StableԤ�⣺
- `�о� YYYY-MM-DD��YYYY-MM-DD`
- `�ɼ���ʷ YYYY-MM-DD��YYYY-MM-DD`
- `�ز��о� YYYY-MM-DD��YYYY-MM-DD`

1. ������ֹ���ڣ������ˣ����31�죩�����ɶ���Ψһrequest_id������research-20260918-a1b2c3d4��
2. ����startHH520Research��ref=main��inputs��request_id��start_date��end_date��
3. ����200��204Ϊ�Ѵ��������ظ��ύ����ȡgetHH520ResearchResult��directory=results��ref=research-results��request_id���ֲ��䡣
4. 404ֻ������δ��������������������������ȷʧ�ܣ�����ʧ�ܣ���������ѯ��
5. ��GitHub����content/encoding=base64��Contents��װ��Ӧ����JSON���ȡ����Ӧ�ṩ��download_url�����ܰѷ�װ���о����档rawý��������Чʱֱ�Ӷ�ȡJSON��
6. ֻ��������ʵ�ʰ����Ĳɼ���Χ����Ⱦ�����������ֲ�����ѡ�۲켰���ơ�û��������ָ֤��ʱ����������ɻز�����������֤��
7. Research���ֻ��research-results��Stable���ֻ��action-results����ѡ��������˹���ˣ������Զ��޸�Stable��

Stable�����ͬ������Contents��װ��Ҳ����ȡ������JSON����������Stable operationId��·����refԼ����
ChatGPT Action�˲���֤֧���Զ���Accept����ͷ������Ӧͨ���༭������ʵ���ú���raw/��װ��Ϊ������/APIͨ�����ܴ���GPT�����ա�
